package cn.yinling.guide;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;
import java.util.*;
import static cn.yinling.guide.ConversationBook.Topic.*;

@Service
public class GuideService {
    private static final Set<String> INTENTS=Set.of("tourism","health","fraud","care","culture","community","volunteer","ability","help");
    private final ScenicDataProvider provider;
    private final OllamaClient model;
    private final AmapPlaces places;
    private final GuideTools guideTools;
    public GuideService(ScenicDataProvider provider,OllamaClient model,AmapPlaces places,GuideTools guideTools) { this.provider=provider; this.model=model; this.places=places; this.guideTools=guideTools; }
    public record Tool(String tool,Map<String,Object> args,Object result) {}
    public record Handoff(String type,String to,String reason) {}
    public record Answer(String intent,String text,double speechRate,String audioUrl,List<Tool> tools,Handoff handoff) {}

    public Answer answer(AgentApi.Message input,ConversationBook.State state) {
        Answer answer=answerCurrent(input,state);
        if(answer.intent().equals("tourism") && !has(input.text(),"重新开始对话","清空对话","忘记刚才"))
            state.remember(input.text(),ReplyText.clean(answer.text()));
        return answer;
    }

    private Answer answerCurrent(AgentApi.Message input,ConversationBook.State state) {
        String text=input.text().strip();
        if(input.intent()!=null && !INTENTS.contains(input.intent())) throw new IllegalArgumentException("intent");
        String intent=isHelp(text)?"help":input.intent()==null?detect(text):input.intent();
        if(intent.equals("help")) {
            state.pending=null; state.lastTopic=null;
            String target=has(text,"家人","家属","女儿","儿子")?"family":"scenic";
            return new Answer(intent,"我理解您需要帮助。当前仅生成转人工请求信息，尚未创建求助事件，也没有通知家属或工作人员。请使用平台求助入口或直接联系身边工作人员。",
                state.speechRate,null,List.of(),new Handoff("human_handoff",target,"老人请求人工帮助"));
        }
        if(has(text,"重新开始对话","清空对话","忘记刚才")) {
            state.reset(); return reply("tourism","已清空本次临时上下文。您想听景点故事，还是查找设施？",state);
        }
        if(!intent.equals("tourism")) {
            state.pending=null; state.lastTopic=null;
            return reply(intent,"该服务暂未开放。现在可以询问清风园演示景点、设施和开放时间。",state);
        }
        String suppliedContext=input.context()==null?null:input.context().location();
        if(has(text,"你能做什么","你能帮我做什么","你可以帮我做什么","介绍你自己","介绍一下你","你有什么功能")) {
            return reply("tourism","我是小颐，可以帮您了解地点、导入攻略、准备含交通与休息建议的出游草案。您可以说目的地和想玩几天；实际开放、预约和无障碍条件需要另行核实。",state);
        }
        if(guideTools.matches(text) && (suppliedContext==null||!suppliedContext.startsWith("spot-")))
            return guideTools.answer(text,suppliedContext,state.queryCity,state.speechRate);
        String requestedPlace=PlaceQuery.extract(text);
        boolean mockNamed=false;
        for(var item:provider.spots())if(text.contains(item.path("name").asText()))mockNamed=true;
        // 已选中高德地点时，针对该地点的提问应进入下方 amap 详情分支，不能重新搜索，
        // 否则「选择并询问」发出的"介绍一下X"会被地点提取拦截，循环回选择列表、讲解永远出不来。
        boolean aboutSelectedPlace=false;
        if(requestedPlace!=null && suppliedContext!=null && suppliedContext.startsWith("amap:")) {
            try { aboutSelectedPlace=requestedPlace.equals(places.detail(suppliedContext.substring(5)).name()); }
            catch(RuntimeException ex) { aboutSelectedPlace=false; }
        }
        if(requestedPlace!=null && !mockNamed && !aboutSelectedPlace)return searchMentionedPlace(requestedPlace,state);
        if(state.queryCity!=null && has(text,"看看景点","有哪些景点","推荐景点","了解美食","看看美食","出游建议")) {
            String category=has(text,"美食")?"美食":"景点";
            return searchMentionedPlace(state.queryCity+category,state);
        }
        String supplied=input.context()==null?null:input.context().location();
        if(input.context()!=null && (supplied==null || supplied.isBlank()) && state.suppliedLocationId!=null) {
            state.suppliedLocationId=null; state.locationId=null; state.discussedSpotId=null;
        }
        if(supplied!=null && !supplied.isBlank() && !supplied.equals(state.suppliedLocationId)) {
            state.suppliedLocationId=supplied; state.locationId=supplied; state.discussedSpotId=null;
        }
        if(supplied!=null && supplied.startsWith("amap:")) {
            if(has(text,"简单点","简短"))state.detailed=false;
            if(has(text,"详细","展开讲"))state.detailed=true;
            if(has(text,"慢点","慢一点"))state.speechRate=.65;
            var place=places.detail(supplied.substring(5));
            var evidence=Map.of("source","AMAP","retrievedAt",java.time.Instant.now().toString(),"places",List.of(place));
            var tools=List.of(new Tool("place.detail",Map.of("id",place.id()),evidence));
            String reference=place.name()+"，地址："+place.address()+"。类别："+place.type()+"。";
            String note="地点资料来自高德；未核实实时营业、历史故事及无障碍条件。地图入口可查看地点并进一步选择路线。";
            String body=reference;
            if(model.enabled()) {
                try { body=ReplyText.clean(model.generate(text,evidence,reference,state.detailed?"DETAILED":"BRIEF")); }
                catch(OllamaClient.Unavailable ex){ body=reference+"\n本地模型暂不可用，先为您展示已查到的地点资料。"; }
            }
            return new Answer("tourism",body+"\n\n"+note,state.speechRate,null,tools,null);
        }
        List<JsonNode> named=new ArrayList<>();
        for(var candidate:provider.spots()) if(text.contains(candidate.path("name").asText())) named.add(candidate);
        if(named.size()>1) {
            state.pending=topic(text);
            return reply("tourism","您提到了多个景点，请先选一个："+String.join("、",named.stream().map(s->s.path("name").asText()).toList())+"。",state);
        }
        JsonNode namedSpot=named.isEmpty()?null:named.get(0);
        boolean styleChange=has(text,"简单点","简单一点","简短","简要","详细","展开讲","多讲一点");
        if(has(text,"简单点","简单一点","简短","简要")) state.detailed=false;
        if(has(text,"详细","展开讲","多讲一点")) state.detailed=true;
        boolean rateChange=has(text,"慢点","慢一点","慢些","慢语速","快一点","正常语速","普通语速");
        if(has(text,"慢点","慢一点","慢些","慢语速")) state.speechRate=.65;
        if(has(text,"快一点","正常语速","普通语速")) state.speechRate=1.0;
        var topic=topic(text);
        if(styleChange && namedSpot==null && !has(text,"故事","介绍","厕所","卫生间","休息","开放","饮水")) topic=state.lastTopic;
        boolean followup=has(text,"继续讲","再讲讲","还有呢","再说一遍");
        if(topic==null && namedSpot!=null && state.pending!=null) topic=state.pending;
        if(topic==null && (styleChange || followup)) topic=state.lastTopic;
        if(topic==null && namedSpot!=null) topic=NARRATION;
        JsonNode spot=namedSpot;
        if(spot==null && has(text,"那里","那儿","那个地方","那边")) spot=spot(state.discussedSpotId);
        if(spot==null && (styleChange || followup)) spot=spot(state.discussedSpotId);
        if(spot==null) spot=spot(state.locationId);
        if(namedSpot!=null && (state.pending!=null || has(text,"我在","现在在","到了","走到"))) state.locationId=namedSpot.path("id").asText();
        if(topic==null) {
            if(rateChange) return reply("tourism","好的，已调整本次对话的语速参数；接入语音播放后生效。",state);
            if(styleChange) return reply("tourism",state.detailed?"好的，我会多讲一些。您想了解哪个景点？":"好的，我会说得简短些。您想问什么？",state);
            if(model.enabled()) return reply("tourism","【本地 AI】"+model.chat(text,List.copyOf(state.recent)),state);
            if(has(text,"谁","名字","称呼")) return reply("tourism","我还没有读取您的个人档案。您愿意告诉我怎么称呼您吗？",state);
            return reply("tourism","我在。您可以告诉我现在想聊什么，也可以问景点或设施；自由聊天需要启用本地模型。",state);
        }
        if(topic==HOURS) {
            state.pending=null; state.lastTopic=HOURS;
            return knowledge(text,"【清风园演示数据】设定开放时间为 "+provider.park().path("hours").asText()+"。这不是实时营业状态，实际开放情况须向景区核实。",
                List.of(provider.park()),state,"这不是实时营业状态，实际开放情况须向景区核实。");
        }
        if(topic==ROUTE) {
            state.pending=null; state.lastTopic=ROUTE;
            return recommendRoute(text,state);
        }
        if(spot==null) return noPlaceYet(topic,text,state);
        state.pending=null; state.lastTopic=topic; state.discussedSpotId=spot.path("id").asText();
        if(topic==NARRATION) {
            String narration=spot.path("narration").asText();
            if(state.detailed) narration+="现有资料仅包含以上介绍，暂时没有更多经过核实的历史细节。您可以继续问这里的休息设施。";
            return knowledge("介绍"+spot.path("name").asText()+"。本轮问题："+text,"【清风园演示讲解】"+narration,List.of(spot),state,"");
        }
        List<JsonNode> matches=new ArrayList<>();
        String type=topic.name().toLowerCase(Locale.ROOT);
        for(var facility:provider.facilities()) if(type.equals(facility.path("type").asText()) && spot.path("id").asText().equals(facility.path("spotId").asText())) matches.add(facility);
        String facts=matches.isEmpty()?"现有演示资料中没有记录"+spot.path("name").asText()+"的"+label(topic)+"，不能据此判断现实中没有设施。"
            :spot.path("name").asText()+"的资料记录："+String.join("；",matches.stream().map(f->f.path("name").asText()+"，"+f.path("note").asText()).toList())+"。";
        String note="";
        if(topic==REST) facts="走累了可以先歇歇。"+facts;
        return knowledge("查询"+spot.path("name").asText()+"的"+label(topic)+"。本轮问题："+text,"【清风园演示数据】"+facts+note,matches,state,note);
    }
    private Answer searchMentionedPlace(String query,ConversationBook.State state){
        String city=state.queryCity==null?"":state.queryCity;
        boolean cityRequest=query.matches(".*(?:省|市|县)$");
        if(cityRequest){state.queryCity=query;city=query;}
        String keyword=cityRequest?"风景名胜":query;
        var found=places.search(keyword,city);
        var evidence=Map.of("source","AMAP","retrievedAt",java.time.Instant.now().toString(),"places",found,"queryPlace",query,"queryCity",city,"requiresSelection",true);
        String body;
        if(found.isEmpty())body="暂时没有查到与“"+query+"”匹配的地点。您可以补充城市或完整名称，不需要开启定位。";
        else if(cityRequest)body="可以，我们先了解“"+query+"”。我查到了这些景点，您想先看看哪一个？也可以接着问“了解美食”。这些是地点资料，城市历史与出游建议还需要补充可靠来源。";
        else body="我为您查询了“"+query+"”。请核对下面的名称和地址，选择要了解的地点，再继续问我。";
        return new Answer("tourism",body,state.speechRate,null,List.of(new Tool("place.search",Map.of("query",query,"city",city),evidence)),null);
    }
    private Answer knowledge(String question,String reference,List<JsonNode> records,ConversationBook.State state,String note) {
        var evidence=Map.of("source","MOCK","records",records);
        var tools=List.of(new Tool("knowledge.search",Map.of("query",question),evidence));
        if(!model.enabled() || records.isEmpty()) return new Answer("tourism",reference,state.speechRate,null,tools,null);
        String generated=ReplyText.clean(model.generate(question,evidence,ReplyText.clean(reference),state.detailed?"DETAILED":"BRIEF"));
        if(generated.isBlank()) throw new OllamaClient.Unavailable("本地模型没有生成有效回答，请重试。");
        return new Answer("tourism","【清风园演示资料 · 本地 AI】"+generated+(note.isEmpty()?"":"\n"+note),state.speechRate,null,tools,null);
    }
    /** 快捷问在没有选中地点时，也要给出可直接使用的内容；但必须先明说不知道位置，且不产生工具调用。 */
    private Answer noPlaceYet(ConversationBook.Topic topic,String text,ConversationBook.State state){
        state.pending=topic;
        if(topic==NARRATION){
            List<JsonNode> spots=new ArrayList<>();
            for(var s:provider.spots()) spots.add(s);
            if(spots.isEmpty()) return reply("tourism","我还不知道您的位置；演示资料里也还没有可介绍的景点。您可以先搜索一个真实地点，我再按查到的资料回答。",state);
            var lines=new ArrayList<String>();
            for(int i=0;i<spots.size();i++) lines.add((i+1)+". "+spots.get(i).path("name").asText()+"："+shorten(spots.get(i).path("narration").asText(),34));
            String body="【清风园演示资料】我还不知道您的位置，先把它能讲的 "+spots.size()+" 个景点列给您：\n"
                +String.join("\n",lines)
                +"\n您挑一个，或者直接告诉我讲哪个，我就展开讲给您听。";
            return reply("tourism",body,state);
        }
        String type=topic.name().toLowerCase(Locale.ROOT);
        List<JsonNode> matches=new ArrayList<>();
        for(var facility:provider.facilities()) if(type.equals(facility.path("type").asText())) matches.add(facility);
        if(matches.isEmpty())
            return reply("tourism","我还不知道您的位置，也就没法判断"+label(topic)+"在哪。演示资料里也没有记录"+label(topic)+"，这不代表现实中就没有；先搜索或选择一个地点，我再按那边的资料回答。",state);
        var where=new HashMap<String,String>();
        for(var s:provider.spots()) where.put(s.path("id").asText(),s.path("name").asText());
        var lines=new ArrayList<String>();
        for(int i=0;i<matches.size();i++){
            var facility=matches.get(i);
            String spotName=where.getOrDefault(facility.path("spotId").asText(),"");
            lines.add((i+1)+". "+facility.path("name").asText()+"（"+(spotName.isEmpty()?"":spotName+"，")+facility.path("note").asText()+"）");
        }
        String body="【清风园演示资料 · 尚未选中真实地点】您想找"+label(topic)+"。我还不知道您的位置，先给您清风园演示园区的 "+matches.size()+" 处记录：\n"
            +String.join("\n",lines)
            +"\n这些是清风园的资料，不代表示您附近的位置；选择或搜索一个真实地点后，我再按那边的资料回答。";
        return reply("tourism",body,state);
    }
    private String shorten(String text,int max){ return text.length()<=max?text:text.substring(0,max)+"…"; }
    private Answer reply(String intent,String text,ConversationBook.State state) { return new Answer(intent,text,state.speechRate,null,List.of(),null); }
    /** Route facts come from the shared fixture; picking by profile stays with P2's route interface. */
    private Answer recommendRoute(String text,ConversationBook.State state) {
        List<JsonNode> routes=new ArrayList<>();
        for(var r:provider.routes()) routes.add(r);
        var evidence=Map.of("source","MOCK","routes",routes);
        var tools=List.of(new Tool("route.recommend",Map.<String,Object>of("query",text,"personalized",false),evidence));
        if(routes.isEmpty()) return new Answer("tourism","演示资料里还没有可介绍的路线。",state.speechRate,null,tools,null);
        var lines=new ArrayList<String>();
        String fewest=null; int fewestSteps=Integer.MAX_VALUE;
        for(var r:routes) {
            int steps=0,minutes=0; var rests=new LinkedHashSet<String>();
            for(var seg:r.path("segments")) {
                steps+=seg.path("steps").asInt();
                minutes+=seg.path("walkMin").asInt();
                for(var f:seg.path("restFacilities")) rests.add(f.asText());
            }
            lines.add(r.path("name").asText()+"约 "+steps+" 级台阶、"+minutes+" 分钟、"+rests.size()+" 处休息点");
            if(steps<fewestSteps) { fewestSteps=steps; fewest=r.path("name").asText(); }
        }
        String body="【清风园演示数据】演示路线共 "+routes.size()+" 条："+String.join("；",lines)
            +"。其中"+fewest+"台阶最少。当前没有更改您的路线。要按您的体力和是否忌台阶挑选一条，还需要读取您的个人档案，这一版还没有接入。";
        return new Answer("tourism",body,state.speechRate,null,tools,null);
    }
    private JsonNode spot(String id) {
        if(id!=null) for(var s:provider.spots()) if(id.equals(s.path("id").asText())) return s;
        return null;
    }
    private ConversationBook.Topic topic(String text) {
        if(has(text,"几点","关门","开门","开放","营业")) return HOURS;
        if(has(text,"厕所","卫生间","洗手间","方便一下","解手")) return TOILET;
        if(has(text,"喝水","饮水","接水","口渴","有水","喝口水")) return WATER;
        if(has(text,"出口","出园","回去")) return EXIT;
        if(!has(text,"不累","不想休息","不用休息") && has(text,"休息","累","歇","椅","腿酸","腿走酸","走不动","坐一会","坐会","能坐","坐坐")) return REST;
        if(has(text,"路线","哪条路","省力","登高","台阶少","台阶多","几级台阶")) return ROUTE;
        if(has(text,"故事","介绍","讲讲","讲解","景点")) return NARRATION;
        return null;
    }
    private String label(ConversationBook.Topic topic) {
        return switch(topic) { case TOILET->"卫生间"; case REST->"休息处"; case WATER->"饮水处"; case EXIT->"出口";
            case ROUTE->"路线"; default->"景点介绍"; };
    }
    private boolean isHelp(String text) {
        String affirmative=text.replace("不用求助","").replace("不需要求助","").replace("没有迷路","").replace("没走丢","");
        return has(affirmative,"救命","求助","迷路","走丢","不舒服","胸痛","喘不过气","呼吸困难","摔倒","摔了","头晕","联系家人","联系家属","找工作人员","人工帮助");
    }
    private String detect(String t) {
        if(has(t,"诈骗","骗钱","防骗")) return "fraud";
        if(has(t,"食谱","养生","血压","用药")) return "health";
        if(has(t,"非遗","剪纸")) return "culture";
        if(has(t,"志愿")) return "volunteer";
        if(has(t,"技能","交换")) return "ability";
        if(has(t,"社区")) return "community";
        if(has(t,"照顾","探视")) return "care";
        return "tourism";
    }
    private boolean has(String text,String... words) { return Arrays.stream(words).anyMatch(text::contains); }
}

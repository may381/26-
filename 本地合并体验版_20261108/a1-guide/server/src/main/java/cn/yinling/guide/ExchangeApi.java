package cn.yinling.guide;

import com.fasterxml.jackson.databind.*;
import org.springframework.web.bind.annotation.*;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.time.format.*;
import java.util.*;

/**
 * 实时汇率。数据来自免 Key 的公开汇率接口（ExchangeRate-API 公共端），
 * 每 6 小时缓存一次；取不到数据时如实报错，绝不返回估算或编造的汇率。
 */
@RestController
public class ExchangeApi {
    private static final List<String> CURRENCIES=List.of("CNY","USD","EUR","JPY","GBP","HKD","KRW","THB","SGD","AUD","MYR","VND","CHF","CAD");
    private static final long TTL=6*60*60*1000L;
    private final ObjectMapper mapper;
    private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private record Snapshot(Map<String,Double> perCny,String updatedAt,long fetched){}
    private volatile Snapshot snapshot;

    public ExchangeApi(ObjectMapper mapper){this.mapper=mapper;}

    @GetMapping("/api/a1/exchange")
    public AgentApi.Envelope exchange(@RequestParam(defaultValue="CNY") String base){
        if(base==null||!base.matches("[A-Za-z]{3}"))throw new IllegalArgumentException();
        base=base.toUpperCase(Locale.ROOT);
        if(!CURRENCIES.contains(base))throw new IllegalArgumentException();
        var snap=load();
        double anchor=snap.perCny().get(base);
        var rates=new TreeMap<String,Double>();
        for(String code:CURRENCIES){
            if(code.equals(base))continue;
            double value=snap.perCny().get(code)/anchor;
            if(Double.isFinite(value)&&value>0)rates.put(code,value);
        }
        return AgentApi.Envelope.ok(Map.of("source","EXCHANGE_RATE_API","base",base,"updatedAt",snap.updatedAt(),"retrievedAt",Instant.now().toString(),"currencies",CURRENCIES,"rates",rates,"stale",System.currentTimeMillis()-snap.fetched()>=TTL,"cachedAt",Instant.ofEpochMilli(snap.fetched()).toString()));
    }

    /** 汇率量级差异很大（VND≈3500、JPY≈23、USD≈0.15），按数量级保留可读精度。 */
    static double round(double value){
        if(value>=1000)return Math.round(value);
        if(value>=100)return Math.round(value*10)/10.0;
        if(value>=1)return Math.round(value*10000)/10000.0;
        return Math.round(value*1000000)/1000000.0;
    }

    private Snapshot load(){
        var current=snapshot;
        if(current!=null&&System.currentTimeMillis()-current.fetched()<TTL)return current;
        synchronized(this){
            current=snapshot;
            if(current!=null&&System.currentTimeMillis()-current.fetched()<TTL)return current;
            try{return fetch();}catch(Exception ex){
                // 数据源不可用但手上还有旧数据：如实返回旧数据自带的时间戳，不冒充实时。
                var stale=snapshot;
                if(stale!=null)return stale;
                if(ex instanceof OllamaClient.Unavailable unavailable)throw unavailable;
                throw new OllamaClient.Unavailable("汇率数据暂时取不到，请稍后重试。");
            }
        }
    }

    private Snapshot fetch()throws Exception{
        var uri=URI.create("https://open.er-api.com/v6/latest/CNY");
        var response=client.send(HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(15)).GET().build(),HttpResponse.BodyHandlers.ofString());
        if(response.statusCode()!=200)throw new OllamaClient.Unavailable("汇率数据源暂时不可用，请稍后重试。");
        var root=mapper.readTree(response.body());
        if(!"success".equalsIgnoreCase(root.path("result").asText()))throw new OllamaClient.Unavailable("汇率数据源返回异常，请稍后重试。");
        var raw=root.path("rates");
        var perCny=new HashMap<String,Double>();
        for(String code:CURRENCIES){
            double value=raw.path(code).asDouble(0);
            if(!(value>0)||!Double.isFinite(value))throw new OllamaClient.Unavailable("汇率数据源缺少"+code+"，暂不能换算。");
            perCny.put(code,value);
        }
        snapshot=new Snapshot(Map.copyOf(perCny),stamp(root.path("time_last_update_utc").asText("")),System.currentTimeMillis());
        return snapshot;
    }

    static String stamp(String raw){
        try{return Instant.from(DateTimeFormatter.ofPattern("EEE, dd MMM yyyy HH:mm:ss Z",Locale.ENGLISH).parse(raw)).toString();}
        catch(Exception ignored){throw new OllamaClient.Unavailable("汇率更新时间无效，暂不能换算。");}
    }
}


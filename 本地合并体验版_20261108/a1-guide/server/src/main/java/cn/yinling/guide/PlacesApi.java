package cn.yinling.guide;
import org.springframework.web.bind.annotation.*;
@RestController
public class PlacesApi {
    private final AmapPlaces places;
    public PlacesApi(AmapPlaces places){this.places=places;}
    @GetMapping("/api/a1/places")
    public AgentApi.Envelope search(@RequestParam String query,@RequestParam(defaultValue="") String city){
        return AgentApi.Envelope.ok(java.util.Map.of("source","AMAP","retrievedAt",java.time.Instant.now().toString(),"places",places.search(query,city)));
    }

    @GetMapping("/api/a1/districts")
    public AgentApi.Envelope districts(@RequestParam(defaultValue="中国") String code){return AgentApi.Envelope.ok(places.districts(code));}
    public record Coordinates(double longitude,double latitude){}
    @PostMapping("/api/a1/location")
    public AgentApi.Envelope locate(@RequestBody Coordinates coordinates){return AgentApi.Envelope.ok(places.locate(coordinates.longitude(),coordinates.latitude()));}

    @GetMapping(value="/api/a1/map-image",produces="image/png")
    public byte[] map(@RequestParam String id,@RequestParam(defaultValue="15") int zoom,@RequestParam(defaultValue="") String nearbyIds){return places.mapImage(id,zoom,nearbyIds);}

    @GetMapping("/api/a1/nearby")
    public AgentApi.Envelope nearby(@RequestParam String id,@RequestParam String category){return AgentApi.Envelope.ok(java.util.Map.of("source","AMAP","centerId",id,"category",category,"places",places.nearby(id,category)));}
    @GetMapping("/api/a1/weather")
    public AgentApi.Envelope weather(@RequestParam String id){return AgentApi.Envelope.ok(places.weather(id));}

    public record GpsRoute(double longitude,double latitude,String destination,String mode){}
    @PostMapping("/api/a1/routes/from-location")
    public AgentApi.Envelope fromLocation(@RequestBody GpsRoute r){return AgentApi.Envelope.ok(places.transportFromGps(r.longitude(),r.latitude(),r.destination(),r.mode()));}

    @GetMapping("/api/a1/transport")
    public AgentApi.Envelope transport(@RequestParam String from,@RequestParam String to,@RequestParam String mode){return AgentApi.Envelope.ok(places.transport(from,to,mode));}
}

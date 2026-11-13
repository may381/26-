package cn.yinling.guide;

import com.fasterxml.jackson.databind.JsonNode;

/** P2 can supply a database-backed implementation without changing the Agent contract. */
public interface ScenicDataProvider {
    JsonNode park();
    JsonNode spots();
    JsonNode facilities();
    /** Shared route sample. The platform route interface stays with P2 (N3). */
    JsonNode routes();
}

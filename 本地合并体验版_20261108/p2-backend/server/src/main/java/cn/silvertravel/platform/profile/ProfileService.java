package cn.silvertravel.platform.profile;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.*;
import cn.silvertravel.platform.profile.persistence.*;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Set;
import java.util.UUID;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class ProfileService {
    private static final Set<String> FIELDS =
            Set.of(
                    "nickname",
                    "age",
                    "residence",
                    "language",
                    "walkSpeed",
                    "walkDurationMin",
                    "avoidSteps",
                    "interests",
                    "interactionPreference",
                    "emergencyContacts");
    private final ProfileMapper mapper;
    private final BusinessAccessPolicy access;
    private final JsonPatchSupport patcher;
    private final ObjectMapper json;
    private final AuditService audit;

    public ProfileService(
            ProfileMapper mapper,
            BusinessAccessPolicy access,
            JsonPatchSupport patcher,
            ObjectMapper json,
            AuditService audit) {
        this.mapper = mapper;
        this.access = access;
        this.patcher = patcher;
        this.json = json;
        this.audit = audit;
    }

    @Transactional(readOnly = true)
    public ProfileView get(String userId) {
        access.requireElderOwner(userId);
        ProfileEntity entity = mapper.findByUserId(userId);
        if (entity == null) {
            throw BusinessException.notFound("老人档案尚未建立");
        }
        return view(entity);
    }

    @Transactional
    public ProfileView patch(String userId, JsonNode patch) {
        return patch(userId, patch, null);
    }

    @Transactional
    public ProfileView patch(String userId, JsonNode patch, Long expectedVersion) {
        var actor = access.requireElderOwner(userId);
        ProfileEntity entity = mapper.lockByUserId(userId);
        boolean creating = entity == null;
        if (expectedVersion != null && (expectedVersion < 0
                || (creating ? expectedVersion != 0 : !expectedVersion.equals(entity.getVersion())))) {
            throw BusinessException.conflict("档案版本已变化，请重新读取后修改；新建版本应为0");
        }
        ProfileFields fields =
                patcher.merge(patch, creating ? null : read(entity), ProfileFields.class, FIELDS);
        if (creating) {
            entity = new ProfileEntity();
            entity.setId(UUID.randomUUID().toString());
            entity.setUserId(userId);
            entity.setVersion(1L);
            entity.setCreatedAt(java.time.Instant.now());
        } else {
            entity.setVersion(entity.getVersion() + 1);
        }
        entity.setUpdatedAt(java.time.Instant.now());
        try {
            entity.setProfileJson(json.writeValueAsString(fields));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Cannot serialize profile", exception);
        }
        if (creating) {
            mapper.insert(entity);
        } else {
            mapper.updateById(entity);
        }
        audit.record(
                actor,
                userId,
                creating ? "PROFILE_CREATED" : "PROFILE_UPDATED",
                "profile",
                entity.getId());
        return ProfileView.of(entity, fields);
    }

    private ProfileFields read(ProfileEntity entity) {
        try {
            return json.readValue(entity.getProfileJson(), ProfileFields.class);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Stored profile is invalid", exception);
        }
    }

    private ProfileView view(ProfileEntity entity) {
        return ProfileView.of(entity, read(entity));
    }
}

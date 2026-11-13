package cn.silvertravel.platform.family;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.*;
import cn.silvertravel.platform.family.FamilyModels.*;
import cn.silvertravel.platform.family.persistence.*;
import cn.silvertravel.platform.profile.persistence.ProfileMapper;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Profile("!bootstrap")
public class FamilyRelationService {
    private static final Set<String> PERMISSIONS =
            Set.of("shareLocation", "shareProgress", "shareAlert", "remotePlanning");
    private final FamilyRelationMapper mapper;
    private final ProfileMapper profiles;
    private final BusinessAccessPolicy access;
    private final AuditService audit;
    private final JsonPatchSupport patcher;

    public FamilyRelationService(
            FamilyRelationMapper mapper,
            ProfileMapper profiles,
            BusinessAccessPolicy access,
            AuditService audit,
            JsonPatchSupport patcher) {
        this.mapper = mapper;
        this.profiles = profiles;
        this.access = access;
        this.audit = audit;
        this.patcher = patcher;
    }

    @Transactional(readOnly = true)
    public List<View> list(String userId) {
        access.requireElderOwner(userId);
        requireProfile(userId);
        return mapper.findByUserId(userId).stream().map(View::of).toList();
    }

    @Transactional
    public View create(String userId, CreateRequest request) {
        var actor = access.requireElderOwner(userId);
        requireProfile(userId);
        FamilyRelationEntity entity = new FamilyRelationEntity();
        entity.setId(UUID.randomUUID().toString());
        entity.setUserId(userId);
        entity.setName(request.name());
        entity.setRelation(request.relation());
        entity.setPhone(request.phone());
        entity.setStatus(Status.PENDING.name());
        apply(entity, Permissions.none());
        mapper.insert(entity);
        audit.record(actor, userId, "FAMILY_RELATION_CREATED", "familyRelation", entity.getId());
        return View.of(entity);
    }

    @Transactional
    public View approve(String userId, String id) {
        return transition(userId, id, Status.PENDING, Status.ACTIVE, "FAMILY_RELATION_APPROVED");
    }

    @Transactional
    public View revoke(String userId, String id) {
        return transition(userId, id, Status.ACTIVE, Status.REVOKED, "FAMILY_RELATION_REVOKED");
    }

    @Transactional
    public View permissions(String userId, String id, JsonNode patch) {
        var actor = access.requireElderOwner(userId);
        FamilyRelationEntity entity = owned(userId, id);
        if (!Status.ACTIVE.name().equals(entity.getStatus())) {
            throw BusinessException.conflict("仅生效中的家属关系可以修改授权");
        }
        Permissions updated =
                patcher.merge(patch, View.of(entity).permissions(), Permissions.class, PERMISSIONS);
        apply(entity, updated);
        mapper.updateById(entity);
        audit.record(actor, userId, "FAMILY_PERMISSIONS_CHANGED", "familyRelation", id);
        return View.of(entity);
    }

    private View transition(String userId, String id, Status from, Status to, String action) {
        var actor = access.requireElderOwner(userId);
        FamilyRelationEntity entity = owned(userId, id);
        if (!from.name().equals(entity.getStatus())) {
            throw BusinessException.conflict("当前家属关系状态不允许此操作");
        }
        entity.setStatus(to.name());
        if (to == Status.REVOKED) {
            apply(entity, Permissions.none());
        }
        mapper.updateById(entity);
        audit.record(actor, userId, action, "familyRelation", id);
        return View.of(entity);
    }

    private FamilyRelationEntity owned(String userId, String id) {
        FamilyRelationEntity entity = mapper.lockOwned(id, userId);
        if (entity == null) {
            throw BusinessException.notFound("家属关系不存在");
        }
        return entity;
    }

    private void requireProfile(String userId) {
        if (profiles.findByUserId(userId) == null) {
            throw BusinessException.notFound("请先建立老人档案");
        }
    }

    private void apply(FamilyRelationEntity entity, Permissions permissions) {
        entity.setShareLocation(permissions.shareLocation());
        entity.setShareProgress(permissions.shareProgress());
        entity.setShareAlert(permissions.shareAlert());
        entity.setRemotePlanning(permissions.remotePlanning());
    }
}

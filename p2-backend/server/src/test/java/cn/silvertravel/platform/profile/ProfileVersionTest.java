package cn.silvertravel.platform.profile;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import cn.silvertravel.platform.audit.AuditService;
import cn.silvertravel.platform.common.api.JsonPatchSupport;
import cn.silvertravel.platform.profile.persistence.*;
import cn.silvertravel.platform.security.BusinessAccessPolicy;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

class ProfileVersionTest {
    @Test
    void staleVersionIsRejectedBeforeMergeOrWrite() throws Exception {
        ProfileMapper mapper = mock(ProfileMapper.class);
        JsonPatchSupport patcher = mock(JsonPatchSupport.class);
        AuditService audit = mock(AuditService.class);
        ProfileEntity entity = new ProfileEntity();
        entity.setVersion(4L);
        when(mapper.lockByUserId("u100")).thenReturn(entity);
        ObjectMapper json = new ObjectMapper();
        ProfileService service = new ProfileService(mapper, mock(BusinessAccessPolicy.class), patcher, json, audit);
        assertThatThrownBy(() -> service.patch("u100", json.readTree("{\"nickname\":\"旧页面\"}"), 3L))
                .hasMessageContaining("档案版本已变化");
        verifyNoInteractions(patcher, audit);
        verify(mapper, never()).updateById(any(ProfileEntity.class));
    }

    @Test
    void creationConditionCannotModifyExistingProfile() throws Exception {
        ProfileMapper mapper = mock(ProfileMapper.class);
        ProfileEntity entity = new ProfileEntity();
        entity.setVersion(1L);
        when(mapper.lockByUserId("u100")).thenReturn(entity);
        ObjectMapper json = new ObjectMapper();
        ProfileService service = new ProfileService(mapper, mock(BusinessAccessPolicy.class), mock(JsonPatchSupport.class), json, mock(AuditService.class));
        assertThatThrownBy(() -> service.patch("u100", json.createObjectNode(), 0L))
                .hasMessageContaining("档案版本已变化");
        verify(mapper, never()).updateById(any(ProfileEntity.class));
    }
}

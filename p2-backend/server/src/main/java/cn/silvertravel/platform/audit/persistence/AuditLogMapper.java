package cn.silvertravel.platform.audit.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.springframework.context.annotation.Profile;

@Mapper
@Profile("!bootstrap")
public interface AuditLogMapper extends BaseMapper<AuditLog> {}

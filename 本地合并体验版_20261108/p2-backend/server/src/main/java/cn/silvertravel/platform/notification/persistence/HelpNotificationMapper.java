package cn.silvertravel.platform.notification.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.util.List;
import org.apache.ibatis.annotations.*;
import org.springframework.context.annotation.Profile;

@Mapper
@Profile("!bootstrap")
public interface HelpNotificationMapper extends BaseMapper<HelpNotificationEntity> {
    @Select(
            """
            SELECT * FROM help_notification WHERE help_event_id=#{helpId}
            ORDER BY CASE phase WHEN 'OPEN' THEN 0 WHEN 'ACKNOWLEDGED' THEN 1 ELSE 2 END,
                     recipient_type, recipient_id
            """)
    List<HelpNotificationEntity> findByHelpId(@Param("helpId") String helpId);

    @Select(
            """
            SELECT * FROM help_notification WHERE status IN ('PENDING','SENT') AND delivery_mode='MOCK'
            ORDER BY created_at,id LIMIT 50 FOR UPDATE SKIP LOCKED
            """)
    List<HelpNotificationEntity> lockPendingBatch();
}

package cn.silvertravel.platform.help.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.util.List;
import org.apache.ibatis.annotations.*;
import org.springframework.context.annotation.Profile;

@Mapper
@Profile("!bootstrap")
public interface HelpEventMapper extends BaseMapper<HelpEventEntity> {
    @Select("SELECT * FROM help_event WHERE id=#{id} FOR UPDATE")
    HelpEventEntity lockById(@Param("id") String id);

    @Select(
            """
            <script>SELECT * FROM help_event
            <if test="userId != null"> WHERE user_id=#{userId} </if>
            ORDER BY created_at DESC, id</script>
            """)
    List<HelpEventEntity> findList(@Param("userId") String userId);
}

package cn.silvertravel.platform.profile.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.springframework.context.annotation.Profile;

@Mapper
@Profile("!bootstrap")
public interface ProfileMapper extends BaseMapper<ProfileEntity> {
    @Select("SELECT * FROM elder_profile WHERE user_id = #{userId}")
    ProfileEntity findByUserId(@Param("userId") String userId);

    @Select(
            "SELECT * FROM elder_profile WHERE user_id = #{userId} FOR UPDATE")
    ProfileEntity lockByUserId(@Param("userId") String userId);
}

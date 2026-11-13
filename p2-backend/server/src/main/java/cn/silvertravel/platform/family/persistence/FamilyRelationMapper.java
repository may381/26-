package cn.silvertravel.platform.family.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.util.List;
import org.apache.ibatis.annotations.*;
import org.springframework.context.annotation.Profile;

@Mapper
@Profile("!bootstrap")
public interface FamilyRelationMapper extends BaseMapper<FamilyRelationEntity> {
    @Select("SELECT * FROM family_relation WHERE user_id = #{userId} ORDER BY id")
    List<FamilyRelationEntity> findByUserId(@Param("userId") String userId);

    @Select("SELECT * FROM family_relation WHERE id = #{id} AND user_id = #{userId} FOR UPDATE")
    FamilyRelationEntity lockOwned(@Param("id") String id, @Param("userId") String userId);
}

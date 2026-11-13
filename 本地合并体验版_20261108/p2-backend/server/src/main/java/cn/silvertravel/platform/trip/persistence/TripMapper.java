package cn.silvertravel.platform.trip.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.*;
import org.springframework.context.annotation.Profile;

@Mapper
@Profile("!bootstrap")
public interface TripMapper extends BaseMapper<TripEntity> {
    @Select(
            """
            <script>SELECT * FROM trip WHERE user_id=#{userId} AND status='FINISHED' AND finished_at IS NOT NULL
            <if test="finishedBefore != null">
            AND (finished_at &lt; #{finishedBefore} OR (finished_at=#{finishedBefore} AND id &lt; #{lastId}))
            </if>
            ORDER BY finished_at DESC,id DESC LIMIT #{limit}</script>
            """)
    java.util.List<TripEntity> findFinishedPage(
            @Param("userId") String userId,
            @Param("finishedBefore") java.sql.Timestamp finishedBefore,
            @Param("lastId") String lastId,
            @Param("limit") int limit);

    @Select("SELECT * FROM trip WHERE id = #{id} AND user_id = #{userId}")
    TripEntity findOwned(@Param("id") String id, @Param("userId") String userId);

    @Select("SELECT * FROM trip WHERE id = #{id} AND user_id = #{userId} FOR UPDATE")
    TripEntity lockOwned(@Param("id") String id, @Param("userId") String userId);

    @Select("SELECT * FROM trip WHERE active_user_id = #{userId}")
    TripEntity findActive(@Param("userId") String userId);

    @Update(
            """
            UPDATE trip SET trip_version=trip_version+1,
            journey_anchor_at=COALESCE(#{anchor,jdbcType=TIMESTAMP},journey_anchor_at)
            WHERE id=#{id}
            """)
    void advanceVersion(@Param("id") String id, @Param("anchor") java.sql.Timestamp anchor);

    @Select("SELECT spot_id FROM trip_skipped_stop WHERE trip_id=#{id} ORDER BY skipped_at,spot_id")
    java.util.List<String> skippedSpots(@Param("id") String id);
}

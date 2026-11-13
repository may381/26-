package cn.silvertravel.platform.audit.persistence;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@ActiveProfiles("local")
@org.springframework.test.annotation.DirtiesContext(
        classMode = org.springframework.test.annotation.DirtiesContext.ClassMode.AFTER_CLASS)
@Testcontainers
@org.springframework.test.context.bean.override.mockito.MockitoBean(
        types = org.springframework.scheduling.TaskScheduler.class)
class DatabaseIntegrationTest {
    @Container
    static final MySQLContainer<?> MYSQL =
            new MySQLContainer<>("mysql:8.4")
                    .withDatabaseName("silver_tourism_test")
                    .withUsername("test_app")
                    .withPassword("test_only_password");

    @DynamicPropertySource
    static void databaseProperties(DynamicPropertyRegistry registry) {
        registry.add(
                "spring.datasource.url",
                () ->
                        MYSQL.getJdbcUrl()
                                + (MYSQL.getJdbcUrl().contains("?") ? "&" : "?")
                                + "connectionTimeZone=UTC&forceConnectionTimeZoneToSession=true");
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
    }

    @Autowired AuditLogMapper mapper;
    @Autowired JdbcTemplate jdbc;

    @Test
    @Transactional
    void migrationAndMapperPreserveAuditAndUtcTimestamp() {
        assertThat(
                        jdbc.queryForObject(
                                "SELECT COUNT(*) FROM flyway_schema_history WHERE version = '1' AND success = 1",
                                Integer.class))
                .isEqualTo(1);
        AuditLog entry = new AuditLog();
        entry.setId(UUID.randomUUID().toString());
        entry.setActorId("test-operator");
        entry.setTargetUserId("test-elder");
        entry.setAction("DATABASE_VERIFY");
        entry.setTargetType("test");
        entry.setTargetId("test-target");
        entry.setResult("SUCCESS");
        entry.setOccurredAt(Instant.parse("2026-10-26T00:00:00.123456Z"));
        assertThat(mapper.insert(entry)).isEqualTo(1);
        AuditLog saved = mapper.selectById(entry.getId());
        assertThat(saved.getActorId()).isEqualTo(entry.getActorId());
        assertThat(saved.getOccurredAt()).isEqualTo(entry.getOccurredAt());
    }
}

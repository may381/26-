package cn.silvertravel.platform.scenic;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.mock;

import cn.silvertravel.platform.common.api.ContractJsonConfiguration;
import cn.silvertravel.platform.scenic.persistence.ScenicDatasetRepository;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.validation.Validation;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.*;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.http.converter.json.Jackson2ObjectMapperBuilder;

class ScenicConfigurationTest {
    private ValidatorFactory validation;
    private ApplicationContextRunner context;

    @BeforeEach
    void context() {
        validation = Validation.buildDefaultValidatorFactory();
        var builder = new Jackson2ObjectMapperBuilder().modules(new JavaTimeModule());
        new ContractJsonConfiguration().strictContractJson().customize(builder);
        var importer = new ScenicDatasetImporter(builder.build(), validation.getValidator());
        context =
                new ApplicationContextRunner()
                        .withUserConfiguration(ScenicConfiguration.class)
                        .withBean(ScenicDatasetImporter.class, () -> importer)
                        .withBean(
                                ScenicDatasetImportService.class,
                                () -> mock(ScenicDatasetImportService.class))
                        .withBean(
                                ScenicDatasetRepository.class,
                                () -> mock(ScenicDatasetRepository.class));
    }

    @AfterEach
    void close() {
        validation.close();
    }

    @Test
    void defaultLoadsMockFixture() {
        context.run(
                application ->
                        assertThat(application.getBean(ScenicDataProvider.class))
                                .isInstanceOf(MockScenicProvider.class));
    }

    @Test
    void realSelectsOnlyDatabaseProvider() {
        context.withPropertyValues("data.source=real")
                .run(
                        application ->
                                assertThat(application.getBean(ScenicDataProvider.class))
                                        .isInstanceOf(DbScenicProvider.class));
    }

    @Test
    void invalidSourceAndMissingFixtureFailStartupRatherThanFallback() {
        context.withPropertyValues("data.source=typo")
                .run(application -> assertThat(application).hasFailed());
        context.withPropertyValues("data.fixture=classpath:missing.json")
                .run(application -> assertThat(application).hasFailed());
    }

    @Test
    void startupImportDoesNotFetchRemoteResources() {
        context.withPropertyValues("data.import-location=https://example.invalid/dataset.json")
                .run(application -> assertThat(application).hasFailed());
    }
}

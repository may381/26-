package cn.silvertravel.platform.agent;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import cn.silvertravel.platform.agent.AgentProtocol.*;
import cn.silvertravel.platform.common.api.BusinessException;
import cn.silvertravel.platform.security.*;
import cn.silvertravel.platform.trip.TripService;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Validation;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.security.access.AccessDeniedException;

class AgentMessageValidationTest {
    @Test
    void invalidRepliesCannotForgeToolsOrReturnAudioAndContextsAreClosed() {
        ObjectMapper json = new ObjectMapper().findAndRegisterModules();
        var fakeCall =
                new ToolCall(
                        "help.create",
                        json.createObjectNode(),
                        json.createObjectNode().put("id", "fake"));
        List<Reply> invalid =
                List.of(
                        new Reply(Intent.tourism, "\u200b\u3000", 0.8, null, List.of(), null),
                        new Reply(Intent.tourism, "bad\u0000reply", 0.8, null, List.of(), null),
                        new Reply(Intent.tourism, "reply", Double.NaN, null, List.of(), null),
                        new Reply(
                                Intent.tourism,
                                "reply",
                                0.8,
                                null,
                                List.of(),
                                new Handoff("human_handoff", HandoffTarget.scenic, "\u200b")),
                        new Reply(Intent.help, "wrong intent", 0.8, null, List.of(), null),
                        new Reply(
                                Intent.tourism,
                                "fake audio",
                                0.8,
                                "https://example.invalid/audio",
                                List.of(),
                                null),
                        new Reply(Intent.tourism, "wrong speed", 5.0, null, List.of(), null),
                        new Reply(
                                Intent.tourism,
                                "fake execution",
                                0.8,
                                null,
                                List.of(fakeCall),
                                null));
        try (var validation = Validation.buildDefaultValidatorFactory()) {
            for (Reply candidate : invalid) {
                var access = mock(BusinessAccessPolicy.class);
                when(access.requireElderOwner("u100"))
                        .thenReturn(new CurrentActor("u100", ActorRole.ELDER, "u100"));
                var registry = new AgentInvocationRegistry();
                var token = new AtomicReference<String>();
                AgentGateway gateway =
                        new AgentGateway() {
                            public Intent classify(Message request, String trace) {
                                return Intent.tourism;
                            }

                            public Reply respond(String id, WireMessage request) {
                                token.set(request.toolContextToken());
                                return candidate;
                            }
                        };
                var service =
                        new AgentMessageService(
                                access,
                                mock(TripService.class),
                                gateway,
                                registry,
                                mock(KnowledgeService.class),
                                json,
                                validation.getValidator());
                assertThatThrownBy(
                                () ->
                                        service.send(
                                                new Message("u100", "hello", Intent.tourism, null),
                                                null))
                        .isInstanceOf(BusinessException.class);
                assertThatThrownBy(
                                () ->
                                        registry.use(
                                                "a1",
                                                token.get(),
                                                "knowledge.search",
                                                grant -> true))
                        .isInstanceOf(AccessDeniedException.class);
            }
        }
    }

    @Test
    void invalidInputNeverReachesAgent() {
        var access = mock(BusinessAccessPolicy.class);
        var gateway = mock(AgentGateway.class);
        var trips = mock(TripService.class);
        try (var validation = Validation.buildDefaultValidatorFactory()) {
            var service =
                    new AgentMessageService(
                            access,
                            trips,
                            gateway,
                            new AgentInvocationRegistry(),
                            mock(KnowledgeService.class),
                            new ObjectMapper(),
                            validation.getValidator());
            for (String text : List.of("\u200b", "\u00a0", "bad\u0000input", "a".repeat(2001))) {
                assertThatThrownBy(() -> service.send(new Message("u100", text, null, null), null))
                        .isInstanceOf(BusinessException.class)
                        .satisfies(
                                error ->
                                        assertThat(((BusinessException) error).status().value())
                                                .isEqualTo(400));
            }
            verifyNoInteractions(gateway, trips);
        }
    }

    @Test
    void mockModeCannotBeEnabledAlongsideProduction() {
        var environment = new MockEnvironment();
        environment.setActiveProfiles("local", "production");
        var properties =
                new AgentProperties(
                        AgentProperties.Mode.mock,
                        "http://127.0.0.1:18001",
                        "http://127.0.0.1:18002",
                        "http://127.0.0.1:18003",
                        "",
                        "",
                        "");
        assertThatThrownBy(
                        () ->
                                new AgentConfiguration()
                                        .agentGateway(
                                                properties,
                                                mock(AgentToolService.class),
                                                new ObjectMapper(),
                                                environment))
                .isInstanceOf(IllegalStateException.class);
    }
}

"""Untrusted JSON plan validation: every rejection branch and accepted boundaries."""
import copy
import unittest
from a1 import DOMAINS, PlanningError, validate_plan


def plan():
    return {"decision": "PLAN", "reply": "待查询", "domains": ["tourism"],
            "steps": [{"id": "s1", "agent": "a1", "domain": "tourism",
                       "goal": "查询建议", "dependsOn": []}], "memoryCandidate": None}


class ValidationTests(unittest.TestCase):
    def reject(self, value, message):
        before = copy.deepcopy(value)
        with self.assertRaises(PlanningError) as caught:
            validate_plan(value)
        self.assertEqual(str(caught.exception), message)
        self.assertEqual(value, before, "validator must not repair or mutate input")

    def test_top_level_object_and_exact_fields(self):
        for value in (None, [], "{}", 1, True):
            with self.subTest(value=value):
                self.reject(value, "模型计划字段不符合约定")
        for field in plan():
            value = plan(); del value[field]
            with self.subTest(missing=field):
                self.reject(value, "模型计划字段不符合约定")
        value = plan(); value["executeUrl"] = "http://invalid"
        self.reject(value, "模型计划字段不符合约定")

    def test_location_type_blank_and_limit(self):
        for location in (1, True, [], {}, "", "  ", "地" * 101):
            value = plan(); value["location"] = location
            with self.subTest(location=location): self.reject(value, "地点字段无效")
        for location in (None, "地" * 100):
            value = plan(); value["location"] = location
            self.assertIs(validate_plan(value), value)

    def test_decision_type_and_enum(self):
        for decision in (None, 1, True, [], {}, "", "plan", "EXECUTE"):
            value = plan(); value["decision"] = decision
            with self.subTest(decision=decision): self.reject(value, "计划类型无效")

    def test_reply_type_blank_and_limit(self):
        for reply in (None, 1, True, [], {}, "", "  ", "字" * 1501):
            value = plan(); value["reply"] = reply
            with self.subTest(reply=reply): self.reject(value, "回复为空或过长")
        value = plan(); value["reply"] = "字" * 1500
        self.assertIs(validate_plan(value), value)

    def test_domains_type_items_count_and_duplicates(self):
        for domains in (None, "tourism", {}, [None], [[]], [True], ["unknown"], list(DOMAINS) + ["tourism"]):
            value = plan(); value["domains"] = domains
            with self.subTest(domains=domains): self.reject(value, "领域无效")
        value = plan(); value["domains"] = ["tourism", "tourism"]
        self.reject(value, "领域重复")
        value = plan(); value.update(decision="ASK", steps=[], domains=list(DOMAINS))
        self.assertIs(validate_plan(value), value)

    def test_steps_type_count_and_decision_relation(self):
        for steps in (None, {}, "steps", [plan()["steps"][0]] * 7):
            value = plan(); value["steps"] = steps
            with self.subTest(steps=steps): self.reject(value, "步骤数量无效")
        value = plan(); value["steps"] = []
        self.reject(value, "计划类型与步骤不一致")
        for decision in ("ASK", "REPLY"):
            value = plan(); value["decision"] = decision
            with self.subTest(decision=decision): self.reject(value, "计划类型与步骤不一致")

    def test_step_object_and_exact_fields(self):
        for step in (None, [], "step", 1):
            value = plan(); value["steps"] = [step]
            with self.subTest(step=step): self.reject(value, "步骤字段无效")
        for field in plan()["steps"][0]:
            value = plan(); del value["steps"][0][field]
            with self.subTest(missing=field): self.reject(value, "步骤字段无效")
        value = plan(); value["steps"][0]["command"] = "run"
        self.reject(value, "步骤字段无效")

    def test_step_id_type_blank_length_and_uniqueness(self):
        for identity in (None, [], 1, True, "", "  ", "x" * 41):
            value = plan(); value["steps"][0]["id"] = identity
            with self.subTest(identity=identity): self.reject(value, "步骤编号无效或重复")
        value = plan(); value["steps"] *= 2
        self.reject(value, "步骤编号无效或重复")
        value = plan(); value["steps"][0]["id"] = "x" * 40
        self.assertIs(validate_plan(value), value)

    def test_domain_and_owner_mapping(self):
        for domain, owner in ((None, "a1"), ([], "a1"), ("unknown", "a1"), ("tourism", None), ("tourism", []), ("tourism", "a2")):
            value = plan(); value["steps"][0].update(domain=domain, agent=owner)
            with self.subTest(domain=domain, owner=owner): self.reject(value, "领域与负责人不一致")
        for domain, owner in DOMAINS.items():
            value = plan(); value["domains"] = [domain]; value["steps"][0].update(domain=domain, agent=owner)
            self.assertIs(validate_plan(value), value)

    def test_goal_type_blank_and_limit(self):
        for goal in (None, 1, True, [], {}, "", "  ", "字" * 1001):
            value = plan(); value["steps"][0]["goal"] = goal
            with self.subTest(goal=goal): self.reject(value, "步骤目标无效")
        value = plan(); value["steps"][0]["goal"] = "字" * 1000
        self.assertIs(validate_plan(value), value)

    def test_dependency_type_unknown_self_forward_and_cycle(self):
        for dependencies in (None, {}, "s1", [None], [[]], [True], ["missing"], ["s1"], ["s2"]):
            value = plan(); value["steps"][0]["dependsOn"] = dependencies
            with self.subTest(dependencies=dependencies): self.reject(value, "依赖不存在、引用自身或产生循环")
        value = plan()
        second = copy.deepcopy(value["steps"][0]); second.update(id="s2", dependsOn=["s1"])
        value["steps"].append(second); value["steps"][0]["dependsOn"] = ["s2"]
        self.reject(value, "依赖不存在、引用自身或产生循环")

    def test_duplicate_dependency(self):
        value = plan(); second = copy.deepcopy(value["steps"][0])
        second.update(id="s2", dependsOn=["s1", "s1"]); value["steps"].append(second)
        self.reject(value, "依赖重复")

    def test_domain_set_missing_or_extra(self):
        for domains in ([], ["fraud"], ["tourism", "fraud"]):
            value = plan(); value["domains"] = domains
            with self.subTest(domains=domains): self.reject(value, "领域与实际步骤不一致")

    def test_reply_domains_empty_but_ask_may_identify_domain(self):
        value = plan(); value.update(decision="REPLY", steps=[])
        self.reject(value, "直接回复不能包含任务领域")
        value["domains"] = []
        self.assertIs(validate_plan(value), value)
        value.update(decision="ASK", domains=["tourism"])
        self.assertIs(validate_plan(value), value)

    def test_memory_type_blank_and_limit(self):
        for memory in (1, True, [], {}, "", "  ", "字" * 1001):
            value = plan(); value["memoryCandidate"] = memory
            with self.subTest(memory=memory): self.reject(value, "记忆候选无效")
        for memory in (None, "字" * 1000):
            value = plan(); value["memoryCandidate"] = memory
            self.assertIs(validate_plan(value), value)

    def test_six_steps_backward_dependencies_and_no_mutation(self):
        value = plan(); value["steps"] = []
        for i in range(6):
            step = copy.deepcopy(plan()["steps"][0])
            step.update(id="s" + str(i), dependsOn=["s" + str(j) for j in range(i)])
            value["steps"].append(step)
        before = copy.deepcopy(value)
        self.assertIs(validate_plan(value), value)
        self.assertEqual(value, before)


if __name__ == "__main__":
    unittest.main()

"""Local, in-process mock coordination. No actual P2/A2/A3 or notifications."""
import copy
import json
import uuid
from a1 import Conversation, PlanningError


class MockGateway:
    """A replaceable mock boundary; not an implementation of the r3 HTTP gateway."""
    def __init__(self):
        self.events = []
        self.effects = {}

    def event(self, agent, phase, summary):
        self.events.append({"sequence": len(self.events) + 1, "mode": "DEMO",
                            "agent": agent, "phase": phase, "summary": summary})

    def courses(self, city):
        self.event("A3", "MOCK_COURSES_RETURNED", "返回固定演示课程，未查询真实活动")
        return [
            {"id": "demo-course-1", "name": "剪纸入门体验（虚构演示）", "city": city,
             "durationMin": 45, "distance": None, "familyAllowed": None, "availability": "DEMO"},
            {"id": "demo-course-2", "name": "传统窗花手作（虚构演示）", "city": city,
             "durationMin": 60, "distance": None, "familyAllowed": None, "availability": "DEMO"}
        ]

    def prepare_care(self, course):
        self.event("A2", "MOCK_CARE_PREPARED", "仅准备演示陪同请求，尚未通知家属")
        return {"confirmationId": str(uuid.uuid4()), "version": 1, "state": "PENDING",
                "mode": "DEMO", "courseId": course["id"], "courseName": course["name"],
                "summary": "仅在本地记录一条家属陪同演示申请；不报名、不发通知、不保存长期记忆"}

    def decide(self, confirmation, approved):
        cid = confirmation["confirmationId"]
        if confirmation["state"] != "PENDING":
            return copy.deepcopy(self.effects.get(cid))
        if not approved:
            confirmation["state"] = "REJECTED"
            self.event("P2-MOCK", "REJECTED", "用户拒绝，未生成演示申请")
            return None
        effect = {"effectId": "demo-effect-" + uuid.uuid4().hex,
                  "mode": "DEMO", "courseId": confirmation["courseId"],
                  "applicationStatus": "DEMO_CREATED", "notificationStatus": "MOCK_NOT_SENT",
                  "bookingStatus": "NOT_BOOKED", "familyAccepted": False}
        self.effects[cid] = effect
        confirmation["state"] = "EXECUTED"
        self.event("P2-MOCK", "DEMO_CREATED", "本地演示记录已生成，没有外部副作用")
        return copy.deepcopy(effect)


class DemoSession:
    def __init__(self, planner=None):
        self.conversation = Conversation(planner)
        self.gateway = MockGateway()
        self.state = "COLLECTING"
        self.courses = []
        self.selected = None
        self.confirmation = None
        self.wants_care = False

    def snapshot(self):
        return {"mode": "LOCAL_MOCK", "state": self.state, "selected": self.selected,
                "confirmation": self.confirmation, "effects": list(self.gateway.effects.values()),
                "events": self.gateway.events, "realBusinessExecuted": False}

    def send(self, text):
        text = text.strip()
        if text == "/cancel":
            if self.confirmation and self.confirmation["state"] == "PENDING":
                self.gateway.decide(self.confirmation, False)
            self.state = "CANCELLED"
            return "已停止本地演示；未发送通知。已生成的演示记录仍可用 /status 查看。"
        if self.state in ("COMPLETE", "CANCELLED"):
            return "这次演示已结束；输入 /status 查看，或 /reset 开始新需求。不会重复执行。"
        if self.state == "WAIT_SELECTION":
            if text not in ("1", "2"):
                return "请输入1或2选择演示课程；/cancel 可停止。尚未报名或通知。"
            self.selected = copy.deepcopy(self.courses[int(text) - 1])
            self.gateway.event("A1", "SELECTED", "用户选择演示课程")
            if not self.wants_care:
                self.state = "COMPLETE"
                return "已选定演示候选；没有报名、实际活动查询或其他操作。"
            self.confirmation = self.gateway.prepare_care(self.selected)
            self.state = "WAIT_CONFIRMATION"
            return ("已选择：" + self.selected["name"] + "。\nA2模拟模块已整理陪同申请。\n"
                    "确认内容：" + self.confirmation["summary"] + "。\n"
                    "输入“同意”记录演示申请，或“拒绝”；这不是正式P1确认接口。")
        if self.state == "WAIT_CONFIRMATION":
            if text not in ("同意", "拒绝"):
                return "请输入“同意”或“拒绝”；未收到明确决定，保持等待，不执行。"
            approved = text == "同意"
            self.gateway.decide(self.confirmation, approved)
            self.state = "COMPLETE"
            if not approved:
                return "已拒绝陪同演示申请，没有报名、通知或长期记忆写入。"
            return "【演示结束】已生成本地演示申请；未通知女儿、未取得家属接受、未报名。真实协作尚未接通。"

        plan = self.conversation.turn(text)
        if plan["decision"] != "PLAN":
            return plan["reply"]
        if "culture" not in plan["domains"]:
            return "本编排演示仅支持剪纸文化课程与家属陪同；其他领域仍可用 a1.py --chat 测试规划。"
        if not plan.get("location"):
            return "课程演示还需要城市；请补充所在城市。"
        # Use original user constraints, not just the model's abbreviated step list.
        original = "\n".join(m["content"] for m in self.conversation.history if m["role"] == "user")
        self.wants_care = "care" in plan["domains"] or any(word in original for word in ("女儿陪", "家人陪", "陪同"))
        self.gateway.event("A1", "MOCK_DELEGATE", "按用户需求调用本地A3替身；不是P2真实委派")
        self.courses = self.gateway.courses(plan["location"])
        self.state = "WAIT_SELECTION"
        rows = ["【固定演示资料】以下并非查到的真实课程："]
        rows.extend("%s. %s · %s分钟 · 城市标签：%s" % (i, c["name"], c["durationMin"], c["city"])
                    for i, c in enumerate(self.courses, 1))
        rows.append("距离、时间、名额和家属入场条件均未核实。输入1或2选择演示候选。")
        return "\n".join(rows)


def main():
    session = DemoSession()
    print("A1本地协作演示 V0.4｜A2/A3/P2均为程序替身，不发任何真实通知")
    print("/status查看步骤与状态；/reset重置；/cancel停止演示；/exit退出")
    while True:
        try:
            text = input("老人：").strip()
            if text == "/exit":
                return
            if text == "/status":
                print(json.dumps(session.snapshot(), ensure_ascii=False, indent=2))
            elif text == "/reset":
                session = DemoSession()
                print("已清空本地演示会话；未改变任何后端数据。")
            elif text:
                if session.state == "COLLECTING" and text != "/cancel":
                    print("正在请求学校模型理解需求…", flush=True)
                print("\n小颐：" + session.send(text) + "\n")
        except PlanningError as error:
            print("本轮未完成：" + str(error) + "；没有执行真实业务，可重试。")
        except (EOFError, KeyboardInterrupt):
            print("\n演示退出。内存状态不保存。")
            return


if __name__ == "__main__":
    main()

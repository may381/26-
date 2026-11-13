import unittest

from p2_client import P2Error
from plan_execution import PlanExecutor, select_dependency_wave


class P2:
    def __init__(self): self.calls=[]
    def register_steps(self,task,key,version,steps):
        self.calls.append(('steps',task,key,version,steps))
        return {'steps':[{'clientStepKey':s['clientStepKey'],'stepId':'step-'+s['clientStepKey'],
                          'prepareKey':'prepare-'+s['clientStepKey']} for s in steps]}
    def prepare_action(self,task,step,payload,key):
        self.calls.append(('action',task,step,payload,key))
        return {'actionId':'action-'+step,'requiresConfirmation':False}
    def delegate(self,conversation,task,action,payload):
        self.calls.append(('delegate',conversation,task,action,payload))
        return {'childTaskId':'child-'+payload['domain'],'parentTaskId':task,
                'targetAgent':payload['targetAgent'],'status':'QUEUED'}


def plan(*steps):
    return {'decision':'PLAN','reply':'准备协作','domains':list(dict.fromkeys(s['domain'] for s in steps)),
            'steps':list(steps),'memoryCandidate':None,'location':None}


class PlanExecutorTests(unittest.TestCase):
    def test_dependency_wave_unlocks_only_after_all_prerequisites(self):
        value = plan(
            {'id':'s1','agent':'a3','domain':'culture','goal':'查课程','dependsOn':[]},
            {'id':'s2','agent':'a2','domain':'care','goal':'查陪同','dependsOn':[]},
            {'id':'s3','agent':'a2','domain':'care','goal':'组合方案','dependsOn':['s1','s2']})
        first = select_dependency_wave(value)
        self.assertEqual([step['id'] for step in first['ready']], ['s1', 's2'])
        waiting = select_dependency_wave(value, completed_step_ids=['s1'], dispatched_step_ids=['s2'])
        self.assertEqual(waiting['ready'], [])
        self.assertEqual(waiting['pendingStepIds'], ['s3'])
        final = select_dependency_wave(value, completed_step_ids=['s1','s2'])
        self.assertEqual([step['id'] for step in final['ready']], ['s3'])

    def test_dependency_failure_blocks_transitive_dependents(self):
        value = plan(
            {'id':'s1','agent':'a3','domain':'culture','goal':'查课程','dependsOn':[]},
            {'id':'s2','agent':'a2','domain':'care','goal':'查陪同','dependsOn':['s1']},
            {'id':'s3','agent':'a2','domain':'care','goal':'组合方案','dependsOn':['s2']})
        wave = select_dependency_wave(value, failed_step_ids=['s1'])
        self.assertEqual(wave['ready'], [])
        self.assertEqual(wave['blockedStepIds'], ['s1','s2','s3'])

    def test_dependency_wave_never_redispatches_active_step(self):
        value = plan({'id':'s1','agent':'a3','domain':'culture','goal':'查课程','dependsOn':[]})
        wave = select_dependency_wave(value, dispatched_step_ids=['s1'])
        self.assertEqual(wave['ready'], [])

    def test_dependency_wave_rejects_unknown_server_state(self):
        value = plan({'id':'s1','agent':'a3','domain':'culture','goal':'查课程','dependsOn':[]})
        with self.assertRaises(P2Error):
            select_dependency_wave(value, completed_step_ids=['other'])

    def test_registers_prepares_and_delegates_two_independent_children(self):
        p2=P2();executor=PlanExecutor(p2)
        value=executor.delegate_children(conversation_id='conv',task_id='root',task_version=3,
            invocation_id='invoke-1',plan=plan(
                {'id':'s1','agent':'a3','domain':'culture','goal':'查询课程','dependsOn':[]},
                {'id':'s2','agent':'a2','domain':'care','goal':'查询陪同','dependsOn':[]}))
        self.assertEqual([item['childTaskId'] for item in value],['child-culture','child-care'])
        self.assertEqual([call[0] for call in p2.calls],['steps','action','delegate','action','delegate'])
        self.assertEqual(p2.calls[0][4][0]['tool'],'agent.delegate')

    def test_request_key_is_stable_for_same_invocation_and_plan(self):
        child={'id':'s1','agent':'a3','domain':'culture','goal':'查询课程','dependsOn':[]}
        keys=[]
        for _ in range(2):
            p2=P2();PlanExecutor(p2).delegate_children(conversation_id='c',task_id='t',task_version=1,
                invocation_id='same',plan=plan(child));keys.append(p2.calls[0][2])
        self.assertEqual(keys[0],keys[1])

    def test_rejects_a1_or_dependent_steps_before_network(self):
        for child in (
            {'id':'s1','agent':'a1','domain':'tourism','goal':'查路线','dependsOn':[]},
            {'id':'s2','agent':'a2','domain':'care','goal':'陪同','dependsOn':['s1']},
        ):
            p2=P2()
            with self.assertRaises(P2Error):
                PlanExecutor(p2).delegate_children(conversation_id='c',task_id='t',task_version=1,
                    invocation_id='i',plan=plan(child))
            self.assertEqual(p2.calls,[])

    def test_invalid_step_mapping_stops_before_actions(self):
        p2=P2();p2.register_steps=lambda *args:{'steps':[]}
        with self.assertRaises(P2Error):
            PlanExecutor(p2).delegate_children(conversation_id='c',task_id='t',task_version=1,
                invocation_id='i',plan=plan({'id':'s1','agent':'a3','domain':'culture','goal':'查','dependsOn':[]}))


if __name__=='__main__':unittest.main()

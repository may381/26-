"""Create a reproducible, allowlisted delivery ZIP; never include databases or credentials.
Run after building an immutable Java release, then pass --jar relative/path.jar.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--jar',required=True);args=parser.parse_args()
    jar=(ROOT/args.jar).resolve()
    jar.relative_to(ROOT)
    with zipfile.ZipFile(jar) as archive:
        assert 'BOOT-INF/classes/cn/yinling/guide/GuideApplication.class' in archive.namelist()
        assert b'HTTP_1_1' in archive.read('BOOT-INF/classes/cn/yinling/guide/OllamaConfig.class')
    files=set()
    for directory in ['a1-guide/server/src','外包A30/anti-fraud/src','外包A30/anti-fraud/public','外包A30/anti-fraud/dist','外包A30/anti-fraud/backend/app','外包A30/anti-fraud/backend/tests']:
        for p in (ROOT/directory).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.db','.sqlite3'}:files.add(p)
    for directory,patterns in [('a1-orchestrator',['*.py','README.md']),('a1-guide/speech',['*.py','*.ps1','*.txt']),('local-asr',['*.py','*.txt','README.md'])]:
        for pattern in patterns:
            files.update(p for p in (ROOT/directory).glob(pattern) if p.is_file())
    explicit=['a1-guide/server/pom.xml','a1-guide/start.ps1','a1-guide/start-school.ps1','a1-guide/start-release.ps1','a1-guide/学校模型接入说明.md',
      '外包A30/anti-fraud/package.json','外包A30/anti-fraud/package-lock.json','外包A30/anti-fraud/index.html','外包A30/anti-fraud/vite.config.ts',
      '外包A30/anti-fraud/tsconfig.json','外包A30/anti-fraud/tailwind.config.js','外包A30/anti-fraud/postcss.config.js',
      '外包A30/anti-fraud/backend/requirements.txt','外包A30/anti-fraud/backend/local_model_smoke.py','外包A30/anti-fraud/backend/real_api_smoke.py','外包A30/anti-fraud/backend/.env.example',
      '外包A30/anti-fraud/start-home-backend.bat','外包A30/anti-fraud/start-school-backend.bat',
      '外包A30/anti-fraud/setup-backend.bat','比赛启动菜单.cmd']
    files.update(ROOT/p for p in explicit if (ROOT/p).is_file());files.add(jar)
    files.update((ROOT/'外包A30/anti-fraud/tools').glob('test-*.cjs'))
    files.update((ROOT/'a1-guide/tools').glob('test-*.cjs'))
    for name in ['比赛候选版_开始使用.md','比赛交付验收单_20261031.md','旅游与反诈_本地验收说明_20261031.md','P2数据库建表字段建议_V1.0_20261031.md','P2结果卡片对接记录_20261031.md','competition_selfcheck.py','school_generation_check.py','real_tourism_smoke.py','build_delivery.py','学校配置反诈HTTP自检.json','学校模型实际生成验收.json','运行自检结果.json','旅游实际HTTP验收结果.json']:
        p=ROOT/'交付文档'/name
        if p.is_file():files.add(p)
    manifest={'createdAt':datetime.now(timezone.utc).isoformat(),'jar':jar.relative_to(ROOT).as_posix(),
      'jarSha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'scope':'LOCAL_COMPETITION_CANDIDATE_NOT_P2_PRODUCTION',
      'generationProvider':'school','generationModel':'qwen3.8-27b','schoolEndToEndVerified':False,'sharedMemoryConnected':False,'realNotificationsConnected':False}
    target=ROOT/'交付文档/release-manifest.json';target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');files.add(target)
    output=ROOT/'交付文档/旅游与反诈_比赛验收候选版.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(files):
            relative=p.relative_to(ROOT)
            assert '.venv' not in relative.parts and 'node_modules' not in relative.parts
            assert p.name not in {'.env','.a1-service-key','config.local.json','amap-local.properties'}
            archive.write(p,relative.as_posix())
        archive.writestr('交付文档/文件SHA256.json',json.dumps({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},ensure_ascii=False,indent=2))
    print(json.dumps({'fileCount':len(files),'zip':str(output),'bytes':output.stat().st_size},ensure_ascii=False))


if __name__=='__main__':main()

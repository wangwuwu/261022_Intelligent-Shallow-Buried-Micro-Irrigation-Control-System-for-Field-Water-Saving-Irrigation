import sys
import os
import textwrap
import re
import random
import subprocess
import shutil
import json
import hashlib
import xml.etree.ElementTree as ET
from openai import OpenAI
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

OPENCODE_CMD = shutil.which('opencode') or shutil.which('opencode.CMD')
CLAUDE_BINARY = shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.exe")  # Path(__file__).resolve().parent / "codex.exe"
CWD = Path(os.getcwd()).resolve()
PARENT_DIR = CWD
# DEEPSEEK_V4_FLASH = "deepseek/deepseek-flash"
# DEEPSEEK_V4_PRO = "deepseek/deepseek-flash"
DEEPSEEK_V4_FLASH = "opencode-go/deepseek-v4.1-flash"
DEEPSEEK_V4_PRO = "opencode-go/deepseek-v4.1-flash"
TIME_RANGE = '不能晚于2026.08.01，不能早于2026.04.01'
IMAGE_GEN = 'gpt image 2.5'

GET_REQUIREMENT_MODEL = 'gpt-6.1-sol'
GET_REQUIREMENT_MODEL_EFFECT = 'high'

GET_SCREENSHOT_MODEL = 'gpt-6.1-sol'
GET_SCREENSHOT_MODEL_EFFECT = 'high'

PREPARE_CONTEXT_MODEL = 'gpt-6.1-sol'
PREPARE_CONTEXT_MODEL_EFFECT = 'xhigh'

GET_HTML_MODEL = 'gpt-6-luna'
GET_HTML_MODEL_EFFECT = 'xhigh'

MERGE_THML_MODEL = 'gpt-6-luna'
MERGE_THML_MODEL_EFFECT = 'max'

REPAIRE_MODEL = 'gpt-6-luna'
REPAIRE_MODEL_EFFECT = 'max'

SCRENSHOT_HTML_MODEL = 'gpt-6-luna'
SCRENSHOT_HTML_MODEL_EFFECT = 'xhigh'


def run_codex(prompt, workdir, model="gpt-6-luna", reasoning_effort='max'):
    os.makedirs(workdir, exist_ok=True)
    cmd = [
        CLAUDE_BINARY,
        'exec',
        '-m', model,
        '-c', f'model_reasoning_effort={reasoning_effort}',
        '-C', workdir,
        '-c', 'project_root_markers=[]',
        '--dangerously-bypass-approvals-and-sandbox',
        prompt
    ]
    # cmd = [OPENCODE_CMD, "run", "--auto","--dir",workdir,"-m", DEEPSEEK_V4_FLASH, '--variant', 'max',"--dangerously-skip-permissions", prompt]

    process = subprocess.Popen(
        cmd,
        cwd=workdir,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    for line in process.stdout:
        print(line)    
    process.wait()
    #if process.wait() != 0:
        #raise RuntimeError(f"页面生成命令失败：{workdir}")


def _validate_shared_statistics(entities, statistics, error_type=ValueError):
    """校验统计来源；entity_type 支持单实体或以 | 分隔的多实体。"""
    for statistic_id, statistic in statistics.items():
        if not isinstance(statistic, dict):
            raise error_type(f'统计项 {statistic_id!r} 格式错误')
        entity_type = statistic.get('entity_type')
        if not isinstance(entity_type, str):
            raise error_type(f'统计项 {statistic_id!r} 的实体类型必须是字符串：{entity_type!r}')
        entity_types = [name.strip() for name in entity_type.split('|')]
        invalid_types = [name for name in entity_types if not name or name not in entities]
        if invalid_types:
            raise error_type(
                f'统计项 {statistic_id!r} 引用了不存在或为空的实体类型：{invalid_types!r}')
        if 'filters' not in statistic or 'aggregation' not in statistic:
            raise error_type(f'统计项 {statistic_id!r} 缺少筛选或聚合规则')


def prepare_shared_context(requirement_file, save_dir):
    """生成供独立页面和合并阶段共用的业务实体及展示规则。"""
    output_dir = Path(save_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    context_path = output_dir / 'shared_context.json'
    requirement_path = Path(requirement_file).resolve()
    if not requirement_path.is_file():
        raise FileNotFoundError(requirement_path)
    requirement_root = ET.parse(requirement_path).getroot()
    screen_ids = {
        screen.get('screen_id')
        for screen in requirement_root.findall('.//screen_manifest/screen')
        if screen.get('screen_id')
    }

    source_sha256 = hashlib.sha256(requirement_path.read_bytes()).hexdigest()
    if context_path.is_file():
        try:
            cached = json.loads(context_path.read_text(encoding='utf-8'))
            if cached.get('source_sha256') == source_sha256:
                validate_stage_outputs('shared_context', output_dir)
                if screen_ids - set(cached['screen_refs']):
                    raise RuntimeError('共享数据缺少需求文档中的页面引用')
                return context_path
        except (ValueError, RuntimeError):
            pass

    prompt = textwrap.dedent(f"""
        读取交互需求文档 {requirement_path}，生成唯一共享数据文件 {context_path}。
        只使用需求文档和当前输出文件，不参考其他项目。禁止使用任何 skill。
        输出必须是 UTF-8 JSON，顶层包含 source_sha256、entities、statistics、screen_refs。
        source_sha256 必须原样写为 {source_sha256}，供下次复用同一需求文档的共享数据。
        entities 按实体类型保存记录；每条记录使用稳定唯一 ID。跨页面引用只用 ID，禁止复制出互相矛盾的实体。
        statistics 是对象，每项至少包含 entity_type、filters、aggregation，并列出从 entities 计算的规则，不能另写独立常量。
        entity_type 必须是字符串：单实体使用 entities 中的一个类型名称；跨实体统计使用 | 分隔多个类型名称，
        例如 "ProductItem|ProductionBatch|MaterialLot"。每个名称都必须是 entities 的实际键，不允许空名称、数组或不存在的类型。
        跨实体统计的 filters、aggregation 和计算规则必须明确各实体集合的匹配、合并或类型选择方式，以及去重依据。
        screen_refs 是对象，按 screen_id 保存 {{"entity_ids": ["..."], "statistic_ids": ["..."]}}；引用必须真实存在。
        screen_manifest 中每个 screen_id 都必须出现在 screen_refs 中；没有共享数据的页面使用两个空列表。
        样例编号必须符合业务格式且不按记录顺序机械递增；样例时间不能以固定分钟、小时或天数递增，仍须满足业务时间先后关系。
        同一统计口径的卡片、列表和分页总数必须可由同一数据集合计算。
        写入文件后重新解析 JSON，并检查实体 ID 唯一、引用存在及统计口径明确。不要生成其他文件。
        如果出现和时间相关字段，必须满足： {TIME_RANGE}
        不生成字体、字号、颜色、控件尺寸、布局、圆角、间距、导航、图标、主题或公共 CSS。
		如果存在表格，表格中至少含有15行数据
        """).strip()
    
    run_codex(prompt, str(output_dir), model=PREPARE_CONTEXT_MODEL, reasoning_effort=PREPARE_CONTEXT_MODEL_EFFECT)
    context = json.loads(context_path.read_text(encoding='utf-8'))
    required = ('entities', 'statistics', 'screen_refs')
    if any(not isinstance(context.get(key), dict) for key in required):
        raise ValueError(f'共享数据缺少必需对象：{context_path}')
    if context.get('source_sha256') != source_sha256:
        raise ValueError('共享数据的需求文档摘要不匹配')
    if screen_ids - set(context['screen_refs']):
        raise ValueError('共享数据缺少需求文档中的页面引用')
    ids = []
    for records in context['entities'].values():
        if not isinstance(records, list):
            raise ValueError('entities 中每种实体必须是记录列表')
        for record in records:
            if not isinstance(record, dict) or not record.get('id'):
                raise ValueError('共享实体记录缺少 id')
            ids.append(str(record['id']))
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('共享实体 ID 为空或重复')
    _validate_shared_statistics(context['entities'], context['statistics'])
    known_ids = set(ids)
    for reference in context['screen_refs'].values():
        if not isinstance(reference, dict):
            raise ValueError('页面引用格式错误')
        entity_ids = reference.get('entity_ids')
        statistic_ids = reference.get('statistic_ids')
        if not isinstance(entity_ids, list) or not isinstance(statistic_ids, list):
            raise ValueError('页面引用缺少实体或统计项列表')
        if any(entity_id not in known_ids for entity_id in entity_ids):
            raise ValueError('页面引用了不存在的实体 ID')
        if any(statistic_id not in context['statistics'] for statistic_id in statistic_ids):
            raise ValueError('页面引用了不存在的统计项')
    return context_path


def validate_stage_outputs(stage, output_dir):
    """验证每个阶段的产物和可机器读取的验收结论。"""
    output_dir = Path(output_dir)
    if stage == 'shared_context':
        path = output_dir / 'shared_context.json'
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError('共享数据文件缺失或为空')
        data = json.loads(path.read_text(encoding='utf-8'))
        if not all(isinstance(data.get(key), dict) for key in ('entities', 'statistics', 'screen_refs')):
            raise RuntimeError('共享数据结构不完整')
        if not data.get('source_sha256'):
            raise RuntimeError('共享数据缺少需求文档摘要')
        if any(not isinstance(records, list) or any(not isinstance(record, dict) for record in records)
               for records in data['entities'].values()):
            raise RuntimeError('共享实体记录格式错误')
        ids = [record.get('id') for records in data['entities'].values() for record in records if isinstance(record, dict)]
        if not ids or any(not entity_id for entity_id in ids) or len(ids) != len(set(ids)):
            raise RuntimeError('共享实体 ID 为空或重复')
        _validate_shared_statistics(data['entities'], data['statistics'], error_type=RuntimeError)
        for reference in data['screen_refs'].values():
            if not isinstance(reference, dict):
                raise RuntimeError('页面引用格式错误')
            if not isinstance(reference.get('entity_ids'), list) or not isinstance(reference.get('statistic_ids'), list):
                raise RuntimeError('页面引用缺少实体或统计项列表')
            if any(entity_id not in ids for entity_id in reference['entity_ids']):
                raise RuntimeError('页面引用了不存在的实体')
            if any(statistic_id not in data['statistics'] for statistic_id in reference['statistic_ids']):
                raise RuntimeError('页面引用了不存在的统计项')
    elif stage == 'html':
        if not any(path.stat().st_size for path in output_dir.glob('*.html') if path.name != 'merge.html'):
            raise RuntimeError('没有生成独立 HTML 页面')
    elif stage == 'merge':
        path = output_dir / 'merge.html'
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError('merge.html 缺失或为空')
    elif stage == 'repair':
        path = output_dir / 'html_acceptance_report_after_fix.md'
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError('修复后验收报告缺失或为空')
        verdict = output_dir / 'html_acceptance_result.json'
        if not verdict.is_file():
            raise RuntimeError('缺少结构化验收结果')
        result = json.loads(verdict.read_text(encoding='utf-8'))
        counts = ('failed', 'blocked', 'not_tested')
        if any(type(result.get(key)) is not int or result[key] < 0 for key in counts):
            raise RuntimeError('结构化验收结果缺少有效计数')
        if result.get('status') != 'PASS' or any(result[key] for key in counts):
            raise RuntimeError(f'修复后验收未通过：{result}')
    elif stage == 'screenshots':
        plan_path = output_dir / '截图任务清单.json'
        if not plan_path.is_file():
            raise RuntimeError('缺少截图任务清单')
        planned = json.loads(plan_path.read_text(encoding='utf-8'))
        path = output_dir / '截图清单.json'
        if not path.is_file():
            raise RuntimeError('缺少截图清单')
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(planned, list) or not planned or not isinstance(manifest, list) or not manifest:
            raise RuntimeError('截图清单为空或格式错误')
        planned_files = [item.get('filename') for item in planned if isinstance(item, dict)]
        if len(planned_files) != len(planned) or len(planned_files) != len(set(planned_files)):
            raise RuntimeError('截图任务清单存在无效或重复文件名')
        result_files = [item.get('filename') for item in manifest if isinstance(item, dict)]
        if len(result_files) != len(manifest) or set(planned_files) != set(result_files):
            raise RuntimeError('截图结果与预定任务不一致')
        planned_by_name = {item['filename']: item for item in planned}
        seen = set()
        for item in manifest:
            if not isinstance(item, dict) or item.get('status') != 'PASS':
                raise RuntimeError(f'存在未完成截图：{item}')
            name = item.get('filename', '')
            if not name or name in seen or Path(name).name != name or not name.endswith('.png') or not re.search(r'[\u4e00-\u9fff]', name):
                raise RuntimeError(f'截图文件名无效或重复：{name}')
            planned_item = planned_by_name[name]
            if not planned_item.get('page_name') or not planned_item.get('expected_state'):
                raise RuntimeError(f'截图任务缺少页面或预期状态：{name}')
            if item.get('page_name') != planned_item['page_name'] or item.get('component_id') != planned_item.get('component_id'):
                raise RuntimeError(f'截图结果与计划的页面或组件不一致：{name}')
            if not item.get('actual_state'):
                raise RuntimeError(f'截图结果缺少实际状态：{name}')
            seen.add(name)
            image = output_dir / name
            if not image.is_file() or not image.stat().st_size:
                raise RuntimeError(f'截图不存在或为空：{image}')
            with image.open('rb') as stream:
                if stream.read(8) != b'\x89PNG\r\n\x1a\n':
                    raise RuntimeError(f'截图不是有效 PNG：{image}')
    else:
        raise ValueError(f'未知阶段：{stage}')


def get_app_screenshots(requirement_file, save_dir):
    os.makedirs(save_dir, exist_ok=True)

    prompt = textwrap.dedent(f"""
        参考 {requirement_file}，使用 {IMAGE_GEN} 生成手机app截图，保存到 {save_dir} 文件夹  
	    - 直接生成848*1618的截图，不要先生成再resize
	    - 不要在子页面的最上方生成标题
	    - 不要生成顶部状态栏和下方菜单栏
	    - 不要先生成代码再截图。每个页面生成一个截图，不要将所有截图合并在一个图片中返回
	    - 登录页截图没有下方菜单栏
	    - 截图中如果出现日期，{TIME_RANGE}
	    - 所有中文文本必须使用 Noto Sans CJK SC 简体中文字形，禁止使用 Noto Sans CJK JP。
	    - 登录模块是一个单独界面
	    - 截图中禁止出现“张三”、“zhangsan”、“12345”这种明显假数据
        - 各个页面之间存在信息交互，对于同一个信息，在不同截图间要保持一致
        - 主内容区上方不要页面描述信息，左上角不要说明性副标题；不要右侧抽屉，相关操作改用居中弹窗或详情页面。
        - 示例编号不要按记录顺序递增，时间不要逐分钟、逐小时或逐天等间隔增加；同一实体及同口径统计在各页保持一致。
        - 图片名称保存为：page_name+'.png', 注意这里的 page_name必须和 {requirement_file} 中保持一致
        - 将 用于生成图片的prompt保存到 {save_dir},文件名为 page_name+'.txt', 注意这里的 page_name必须和 {requirement_file} 中保持一致
        - 禁止参考其他文件和其他skill
        - 不要使用 superpowers、ui-ux-pro-max
        - 禁止使用深色背景
        - 不要在图片上方生成 页面名称
        - 【跨页面公共组件一致性】

            所有页面必须使用同一套 UI 设计语言。

            多个页面重复出现的公共组件必须保持完全一致，不得每个页面重新设计，包括：

            返回按钮
            主按钮 / 次按钮
            输入框 / 搜索框 / 下拉框
            Tab
            卡片
            Dialog / Drawer
            图标按钮
            Badge / Tag

            要求：

            相同功能组件在不同页面中的形状、圆角、颜色、边框和图标风格保持一致。
            第一次确定某公共组件样式后，后续所有页面必须复用该样式，不得重新设计。
            同一业务动作必须使用相同组件，例如“返回”在所有二级页面必须使用同一种返回控件。
            生成第一张页面后，应将已经确定的公共组件样式视为本次任务的全局 UI 基准；后续页面必须沿用，不得重新推导。
        """).strip()
    cmd = [
            CLAUDE_BINARY,
            'exec',
            '-m', GET_SCREENSHOT_MODEL,
            '-c', f'model_reasoning_effort={GET_SCREENSHOT_MODEL_EFFECT}',
            '-C', CWD,
            '-c', 'project_root_markers=[]',
            '--dangerously-bypass-approvals-and-sandbox',
            prompt
        ]
    process = subprocess.Popen(
            cmd,
            cwd=save_dir,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    process.wait()


def get_win_screenshots(requirement_file, context_file, save_dir, template_img):
    os.makedirs(save_dir, exist_ok=True)

    prompt = textwrap.dedent(f"""
        参考 {requirement_file}和全局唯一共享数据文件 {context_file}，以 {template_img}为UI模版，使用 {IMAGE_GEN} 生成 windows应用 截图，保存到 {save_dir} 文件夹  
        - 从 {context_file} 获取并使用实体数据，并保证全局一致
	    - 直接生成截图，不要先生成再resize
	    - 不要生成导航栏
	    - 不要先生成代码再截图。每个页面生成一个截图，不要将所有截图合并在一个图片中返回
	    - 截图中如果出现日期，{TIME_RANGE}
	    - 所有中文文本必须使用 Noto Sans CJK SC 简体中文字形，禁止使用 Noto Sans CJK JP。
	    - 登录模块是一个单独界面
	    - 截图中禁止出现“张三”、“zhangsan”、“12345”这种明显假数据
        - 各个页面之间存在信息交互，对于同一个信息，在不同截图间要保持一致
        - 主内容区上方不要页面描述信息，左上角不要说明性副标题；不要右侧抽屉，相关操作改用居中弹窗或详情页面。
        - 示例编号不要按记录顺序递增，时间不要逐分钟、逐小时或逐天等间隔增加；同一实体及同口径统计在各页保持一致。
        - 图片名称保存为：page_name+'.png', 注意这里的 page_name必须和 {requirement_file} 中保持一致
        - 将 用于生成图片的prompt保存到 {save_dir},文件名为 page_name+'.txt', 注意这里的 page_name必须和 {requirement_file} 中保持一致
        - 禁止参考其他文件和skill
        - 不要使用 superpowers、ui-ux-pro-max
        - 生成截图的布局、色彩、阴影、线条、圆直角、边框、图标风格、字体和{template_img}保持一致
        - 不要在图片左上方和上方生成 页面名称
        - 禁止出现任何“模拟”、“合成”字样
        - 注意这是一个windows应用的截图，不是web风格的，组件种类和布局要符合windows应用的习惯与规范
 
        """).strip()
    cmd = [
            CLAUDE_BINARY,
            'exec',
            '-m', GET_SCREENSHOT_MODEL,
            '-c', f'model_reasoning_effort={GET_SCREENSHOT_MODEL_EFFECT}',
            '-C', CWD,
            '-c', 'project_root_markers=[]',
            '--dangerously-bypass-approvals-and-sandbox',
            prompt
        ]

    process = subprocess.Popen(
            cmd,
            cwd=save_dir,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
    for line in process.stdout:
        print(line)
    process.wait()


def get_web_screenshots(requirement_file,context_file, save_dir):
    os.makedirs(save_dir, exist_ok=True)

    prompt = textwrap.dedent(f"""
        参考UI交互需求文档 {requirement_file} 和 全局唯一共享数据文件 {context_file}，使用 {IMAGE_GEN} 生成web截图，保存到 {save_dir} 文件夹 
        - 从 {context_file} 获取并使用实体数据，并保证全局一致
	    - 直接生成截图，不要先生成再resize
	    - 不要生成导航栏
	    - 不要先生成代码再截图。每个页面生成一个截图，不要将所有截图合并在一个图片中返回
	    - 截图中如果出现日期，{TIME_RANGE}
	    - 所有中文文本必须使用 Noto Sans CJK SC 简体中文字形，禁止使用 Noto Sans CJK JP。
	    - 登录模块是一个单独界面
	    - 截图中禁止出现“张三”、“zhangsan”、“12345”这种明显假数据
        - 各个页面之间存在信息交互，对于同一个信息，在不同截图间要保持一致
        - 主内容区上方不要页面描述信息，左上角不要说明性副标题；不要右侧抽屉，相关操作改用居中弹窗或详情页面。
        - 示例编号不要按记录顺序递增，时间不要逐分钟、逐小时或逐天等间隔增加；同一实体及同口径统计在各页保持一致。
        - 图片名称保存为：page_name+'.png', 注意这里的 page_name必须和 {requirement_file} 中保持一致
        - 将 用于生成图片的prompt保存到 {save_dir},文件名为 page_name+'.txt', 注意这里的 page_name必须和 {requirement_file} 中保持一致
        - 只参考需求文档、共享数据，不参考其他项目和skill
        - 不要使用 superpowers、ui-ux-pro-max
        - 不要在图片左上方和上方生成 页面名称
        - 禁止出现任何“模拟”、“合成”字样
        - 相同层级的组件、文字使用相同的大小
		- 生成前一次性确定公共UI规范，明确公共区域的位置尺寸、字体字号、按钮和输入框样式、图标形状及笔画。每张图片的prompt原样复用这份规范，不逐页重新设计。只改变业务内容、页面标题文字和导航选中项，公共区域不得增删图片或改变样式
        - 生成后跨页检查公共区域，发现不一致就修正

        """).strip()
    cmd = [
            CLAUDE_BINARY,
            'exec',
            '-m', GET_SCREENSHOT_MODEL,
            '-c', f'model_reasoning_effort={GET_SCREENSHOT_MODEL_EFFECT}',
            '-C', CWD,
            '-c', 'project_root_markers=[]',
            '--dangerously-bypass-approvals-and-sandbox',
            prompt
        ]

    process = subprocess.Popen(
            cmd,
            cwd=save_dir,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    process.wait()


def screenshot_html(html_path, save_dir, cate='web', tool='opencode'):
    os.makedirs(save_dir, exist_ok=True)
    if not Path(html_path).is_file():
        raise FileNotFoundError(html_path)
    
    prompt = textwrap.dedent(f"""
        任务：对指定的html执行自动化页面遍历、交互操作和截图，并将所有最终截图保存到指定文件夹。

        必须实际执行任务，不要只分析、说明方案或输出示例代码。可以编写并运行必要的 Python / Playwright 脚本完成任务。优先通过 DOM 结构、文本、role、class、id、aria 属性等确定元素，不要仅凭视觉猜测。

        ## 一、总体目标

        需要完整遍历 html 中实际可访问的所有业务页面，并对以下状态生成截图：

        如果实际页面出现右侧抽屉，记录为布局验收失败并继续收集证据；不得把它当作合规详情或表单状态。

        1. 每个页面的基础状态；
        2. 页面存在搜索框或筛选框时，输入内容后的状态；
        3. 页面存在 Tab 时，每个 Tab 切换后的状态；
        4. 页面存在可打开 Dialog、Drawer、Modal、表单、详情面板等组件的主要操作按钮时，打开后的状态。
        5. 每个已识别表单中的保存、提交、确认按钮点击后的实际结果（不包括取消、重置、添加、删除按钮）；按适用情况为合法提交成功（不包括必填校验失败、取消恢复）。

        所有用于触发目标状态的关键组件，需要在最终保存的截图中绘制红色矩形框。

        不得只对工作台截图，不得只处理第一个页面，不得遗漏已经能够从当前 HTML 中访问到的页面。

        ---

        ## 二、执行原则

        ### 1. 先扫描，再截图

        正式截图前，先分析 HTML 和页面运行状态，建立内部截图任务清单，包括：

        * 页面名称；
        * 页面入口元素；
        * 页面主标题；
        * 页面搜索/筛选组件；
        * 页面 Tab；
        * 页面主要操作按钮；
        * 操作后可能出现的 Dialog / Drawer / Modal / Form / Detail Panel；
        * 每项对应的计划截图文件名。
        * 表单内部的保存、提交、确认按钮点击后状态。

        将完整计划写入 截图/截图任务清单.json；每项包含 page_name、component_id、expected_state、filename，均使用中文可读名称。
        对所有可访问且应处理的状态先建计划，再执行截图；失败项仍保留在计划和结果中，不得从分母删除。

        完成清单后立即继续执行，不需要等待人工确认。

        不要仅根据静态 HTML 判断页面数量；如果页面通过 JavaScript、Store、Router、Tab、按钮切换，需要结合实际运行状态识别。

        ---

        ### 2. 不修改原业务行为

        允许为了自动化截图：

        * 创建临时测试脚本；
        * 创建临时辅助 CSS；
        * 获取 DOM bounding box；
        * 对最终 PNG 做后处理；
        * 临时注入定位标记。

        但不得破坏或永久修改 html 的：

        * 页面结构；
        * Store；
        * Router；
        * 原交互逻辑；
        * CSS 视觉效果；
        * 数据逻辑。

        如必须临时修改页面才能截图，应优先使用运行时注入，不要直接改动源 HTML。

        ---

        ## 三、页面基础截图

        从工作台或系统主入口开始，识别所有能够进入独立业务页面的入口，例如：

        * 顶部按钮；
        * 导航按钮；
        * 卡片；
        * 菜单项；
        * 页面入口链接。

        对于每个页面：

        1. 定位对应入口；
        2. 获取该入口元素的 bounding box；
        3. 点击入口进入目标页面；
        4. 等待页面完成渲染；
        5. 确认目标页面已经真正显示；
        6. 生成目标页面截图；
        7. 在最终截图中，对“触发进入该页面的入口组件”绘制红框。

        红框要求：

        * 颜色：纯红色 `#FF0000`；
        * 线宽：3px；
        * bounding box 四周向外扩展约 8px；
        * 不遮挡组件主体内容。

        如果进入目标页面后，原入口仍然显示在当前截图内，则必须在该入口上画红框。

        如果页面切换后入口已经完全不可见，则不要为了画红框强行破坏页面布局；此时直接保存目标页面截图，并在最终日志中注明入口在目标状态下不可见。

        基础截图文件名：

        `页面名.png`

        例如：

        `工作台.png`
        `实时监测.png`
        `历史记录.png`

        ---

        ## 四、搜索框 / 筛选框截图

        如果某页面存在搜索框、筛选输入框或主要文本过滤框：

        1. 优先选择页面中的主搜索/主筛选输入框；
        2. 若输入框已有合理业务数据可用于筛选，优先输入能够产生实际筛选结果的值；
        3. 如果无法确定有效业务值，则输入 `测试`；
        4. 输入后触发必要的 input/change/search/Enter 行为；
        5. 等待页面筛选结果更新完成；
        6. 获取该筛选框 bounding box；
        7. 对当前页面截图；
        8. 在最终 PNG 中对该筛选框绘制红框。

        文件名：

        `页面名_筛选.png`

        如果页面存在多个独立且业务意义不同的主要筛选组件，且操作后会产生明显不同状态，可以分别截图：

        `页面名_筛选_筛选名称.png`

        不要为每一个普通 input 都生成截图。

        ---

        ## 五、Tab 截图

        如果页面存在 Tab：

        1. 找到全部实际可点击的可见 Tab；
        2. 包括默认激活 Tab；
        3. 依次点击每一个 Tab；
        4. 每次点击后等待 Tab 内容区域稳定；
        5. 确认对应内容已经切换；
        6. 获取当前 Tab 的 bounding box；
        7. 截图；
        8. 在最终 PNG 中对当前 Tab 绘制红框。

        每个 Tab 必须单独生成截图。

        文件名：

        `页面名_标签名称.png`

        例如：

        `设备详情_实时数据.png`
        `设备详情_历史趋势.png`
        `设备详情_报警记录.png`

        不得只截图默认 Tab。

        ---

        ## 六、按钮触发的 Dialog / Drawer / Form / Detail 截图

        识别页面中能够产生新的明显界面状态的主要按钮，例如：

        * 新增；
        * 创建；
        * 编辑；
        * 查看；
        * 详情；
        * 配置；
        * 设置；
        * 分配；
        * 导入；
        * 导出配置；
        * 审核；
        * 处理；
        * 校准；
        * 启动；
        * 查看报告；
        * 下载
        * 其他会打开 Dialog / Drawer / Modal / Form / Detail Panel 的业务按钮。

        对于每个此类主要操作：

        1. 定位按钮；
        2. 记录按钮 bounding box；
        3. 点击按钮；
        4. 等待弹窗、抽屉、表单或详情面板完全显示；
        5. 确认对应 Overlay 或内容区域真实存在；
        6. 截图；
        7. 如果触发按钮在当前截图中仍然可见，则在该按钮上绘制红框；
        8. 如果按钮被 Overlay 遮挡或已经不可见，则不要强行移动弹窗或改变原页面，仅保存打开后的真实状态。

        文件名优先使用弹出内容的标题：

        `页面名_表单名称.png`

        例如：

        `设备管理_新增设备.png`
        `设备管理_编辑设备.png`
        `任务管理_任务详情.png`

        如果无法获取弹窗/表单标题，则使用触发按钮文字：

        `页面名_按钮名称.png`

        截图后关闭当前 Overlay，恢复页面到稳定状态，再继续下一个操作。

        ## 六点一、表单内按钮点击后的截图

        对保存、提交、确认、上传、预览按钮建立操作清单（不包括取消、重置、添加行、删除行这些按钮）。
        每项用例从确定的页面与数据状态开始，操作后等待真实业务结果稳定，再截图。
        对保存和提交合法提交成功。
        触发二次确认时需截图确认界面及确认或取消后的结果。操作失败应记录实际错误原因，不得用点击前表单截图冒充结果。
        按钮点击后截图使用中文文件名：`页面名称_表单名称_按钮名称_操作结果.png`。
        无表单时省略表单名称；同名结果优先补充业务对象名称，仍重复再追加序号。
        例如：`设备管理_新增设备_保存_必填项校验失败.png`、`设备管理_新增设备_保存_保存成功.png`。
        screen_id、component_id 只写入截图任务清单用于追溯，不用于文件名。
        用例间恢复确定的初始状态，避免前一个写操作影响后续截图。

        ---

        ## 七、不要截图的普通交互

        除非会产生明显的新页面状态，否则不要为以下普通操作单独截图：

        * 返回；
        * 关闭；
        * 不影响表单或业务状态的普通取消；
        * 不影响表单或业务状态的普通确认；
        * 单纯 hover；
        * 无状态变化按钮；
        * 纯刷新；
        * 普通分页下一页；
        * 无业务意义的小图标按钮。

        但如果这些控件会进入新的业务页面、打开新的 Overlay 或显著改变页面内容，则仍需处理。

        ---

        ## 八、截图方式

        优先使用 Playwright。

        建议：

        * 浏览器：Chromium；
        * deviceScaleFactor：1；
        * 保持所有截图尺寸规则一致。
        * screenshot scale = "css"
        * 如果当前html是 手机app， viewport = 848×1618 CSS px，否则 viewport = 1440×900 CSS px
        * 检查页面声明使用的中文字体是否在 Chromium 运行环境中可用，如果不可用你需要先安装字体。

        如果页面内容高度超过 viewport：

        * full_page=True
        * 同一批截图尽量保持一致策略。

        截图前：

        1. 等待 DOMContentLoaded；
        2. 等待当前页面主要内容显示；
        3. 等待动画结束；
        4. 等待 loading / spinner 消失；
        5. 默认额外等待约 500ms；
        6. 有明显异步操作时可等待 1000~1500ms；
        7. 不要使用固定超长 sleep 替代状态判断。
        
        禁止：
        - resize
        - thumbnail
        - CSS transform scale
        - 截图后缩放到目标尺寸
        - JPEG 中间转换
        - 通过缩小 viewport 并提高 DPR 冒充目标尺寸
        
        ---

        ## 九、红框绘制方式

        红框必须存在于最终保存的 PNG 文件中。

        推荐流程：

        1. 使用 Playwright 获取目标元素 `bounding_box()`；
        2. 完成原始截图；
        3. 使用 Pillow 或等价图像处理方式在 PNG 上绘制红框；
        4. 红框坐标相对目标元素四周外扩约 8px；
        5. 线宽 3px；
        6. 对坐标进行图片边界裁剪，避免超出截图。


        不得仅：

        * 使用 CSS outline 后不确认最终截图；
        * 在浏览器中临时高亮但最终 PNG 没有红框；
        * 凭估计手动画框；
        * 使用固定坐标。

        必须基于实际 DOM bounding box。

        ---

        ## 十、页面名称识别

        页面名按以下优先级确定：

        # 1. 当前页面明确主标题；
        2. 工作台或导航中的入口名称；
        3. 面包屑最后一级；
        4. 页面内部独立 section 的业务名称；
        5. 实在无法识别时使用 `未命名页面01`、`未命名页面02` 等中文名称。

        不要使用无意义 DOM id 作为最终页面名称。

        ---

        ## 十一、文件命名

        全部保存到：

        `截图/`

        文件名规则：

        基础页面：
        `页面名.png`

        筛选：
        `页面名_筛选.png`

        Tab：
        `页面名_标签名称.png`

        弹窗/表单：
        `页面名_表单名称.png`

        表单按钮点击后：
        `页面名称_表单名称_按钮名称_操作结果.png`

        所有非法文件名字符：

        `\\ / : * ? " < > |`

        统一替换为 `_`。

        需要去除首尾空格。

        如果文件名重复，追加：

        `_2`
        `_3`

        不得覆盖之前已经生成但语义不同的截图。

        ---

        ## 十二、状态恢复

        每完成一种交互截图后，需要恢复到适合继续操作的页面状态。

        例如：

        * 筛选完成后，可清除筛选再测试 Tab；
        * 一个 Tab 截图完成后继续下一个 Tab；
        * Dialog 截图完成后关闭 Dialog；
        * Drawer 截图完成后关闭 Drawer；
        * 一个页面完成后再进入下一个页面。

        不得因为前一个交互状态残留而导致后续截图失真。

        ---

        ## 十三、异常处理

        任何单项失败都不得直接终止整个任务。

        对于：

        * selector 无法定位；
        * 元素被遮挡；
        * click 无效；
        * 页面没有切换；
        * Overlay 没出现；
        * screenshot 失败；
        * bounding box 获取失败；

        先分析原因并尝试修复。

        允许：

        * 改用 role/text/css locator；
        * scrollIntoView；
        * 等待动画；
        * 重试点击；
        * 检查 Store / DOM；
        * 使用 JavaScript 触发真实事件。

        单个操作最多合理重试 2 次。

        仍失败时：

        1. 记录失败项；
        2. 记录具体原因；
        3. 继续其他页面和其他截图。

        ---

        ## 十四、截图完整性校验

        执行完成后必须自动检查 保存截图 的文件夹。

        至少验证：

        1. 每个已识别页面是否至少存在一张基础截图；
        2. 每个已识别 Tab 是否存在对应截图；
        3. 每个实际处理过的筛选框是否存在筛选截图；
        4. 每个成功打开的主要 Dialog / Drawer / Form 是否存在对应截图；
        4.1 截图任务清单中的每个表单按钮操作及点击后状态是否有对应截图，失败项不得漏报；
        5. PNG 文件是否真实存在且文件大小 > 0；
        6. 是否存在明显重复文件名覆盖；
        7. 红框截图是否真实完成后处理。

        如果发现计划截图缺失，应尝试补截，而不是直接结束。

        ---

        ## 十五、执行日志

        最终输出简洁的执行报告，包括：

        * 识别页面总数；
        * 成功截图总数；
        * 每个页面生成的截图文件；
        * 每页识别出的：

          * 筛选框；
          * Tab；
          * Dialog / Drawer / Form 入口；
        * 失败截图；
        * 失败原因；
        * `截图` 文件夹实际最终文件数量。
        * 截图任务清单数量、已完成数量、未完成的表单按钮及原因。

        同时写入 截图/截图清单.json：顶层为数组，每项包含 filename、status（PASS 或 FAIL）、page_name、component_id、actual_state、failure_reason。
        每个截图任务清单条目都要有且仅有一个结果条目；只有真实 PNG 已存在且操作结果正确才能标记 PASS。

        不要只输出“任务完成”。

        ---

        ## 十六、完成条件

        只有同时满足以下条件，任务才算完成：

        * 所有可访问业务页面均已遍历；
        * 每个页面至少有基础截图；
        * 所有需要处理的 Tab 均已截图；
        * 主要筛选状态已截图；
        * 主要弹窗/表单/抽屉状态已截图；
        * 红框已经实际写入最终 PNG；
        * 所有截图已保存到 `截图` 文件夹；
        * 对截图文件进行了最终完整性校验。

        在满足上述条件前，不要提前宣布完成。
        

       
       待截图的html路径:{html_path}
       业务输入仅限 {html_path}；允许创建、读取本次截图、截图任务清单、截图结果清单和自动化测试脚本。
    """).strip()


    if cate == '手机app':
        prompt = prompt + '\n每个截图间隔至少10秒'
    
    # 这里使用deepseek-v4-flash 进行截图
    if tool=='opencode':
        cmd = [OPENCODE_CMD, "run", "--auto","--dir",CWD,"-m", DEEPSEEK_V4_FLASH, '--variant', 'max',"--dangerously-skip-permissions", prompt]
    else:
        cmd = [
                CLAUDE_BINARY,
                'exec',
                '-m', SCRENSHOT_HTML_MODEL,
                '-c', f'model_reasoning_effort={SCRENSHOT_HTML_MODEL_EFFECT}',
                '-C', CWD,
                '-c', 'project_root_markers=[]',
                '--dangerously-bypass-approvals-and-sandbox',
                prompt
            ]
    process = subprocess.Popen(
        cmd,
        cwd=save_dir,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,

    )

    for line in process.stdout:
        print(line, end="")
    process.wait()
    #if process.wait() != 0:
        #raise RuntimeError('页面截图命令失败')
    # validate_stage_outputs('screenshots', save_dir)
    
    
def get_requirement(template, name, save_dir, cate='web'):
    os.makedirs(save_dir, exist_ok=True)
    assert cate in ['web','手机app','windows应用']

    prompt = textwrap.dedent(f'''
        我会提供一份完整的 XML 前端交互需求文档模板、开发规范以及一个目标系统名称。

        要求：

        1. **保留模板全部关键 XML 标签、章节结构、Schema、Registry、Contract 和字段名称，不得删除、改名或简化。**

        2. 不要简单进行关键词替换。模板中的“实验室、样品、危险品、库位、项目”等属于原业务内容，必须根据 目标系统 重新分析和设计。

        3. 根据目标业务重新推导：

        * 用户角色
        * 业务模块
        * 页面数量
        * 页面层级
        * 导航结构
        * 页面组件
        * 页面状态
        * 业务流程
        * 数据实体
        * 枚举
        * Action
        * Transaction
        * Selector
        * Query
        * Branch
        * Overlay
        * Page Lifecycle
        * 权限
        * 异常处理
        * 验收规则

        4. **页面数量、模块数量、组件数量、Interaction 数量不得照抄模板。**
        例如模板中的 `expected_screen_count="23"`、`migrated_count="67"` 都必须根据新系统实际结果重新计算。

        5. `screen_manifest` 中每个页面必须完整定义模板要求的字段，包括：
        `screen_id`、`page_name`、`html_file`、`route`、`parent_screen_id`、`role`、`back_fallback`、`layout_type`、`task_family`、`primary_interaction_surface`、`ordered_functional_regions`、`navigation_pattern`、`action_placement`、`secondary_surface`、`detail_opening_mode`、`composition_difference` 等。

        6. **所有页面中的可操作组件都必须在 `screen_component_contracts` 中定义完整行为。**
        包括按钮、搜索、筛选、Tab、列表项、卡片、返回、扫码、表单、弹窗、抽屉、分页、行操作等。

        7. 每个 Component 必须明确：
        `component_id`、`match_mode`、`match`、`element_kind`、`event`、`action_type`、`preconditions`、`dialog_id`、`target_screen_id`、`route_params`、`immediate_feedback`、`data_consequence`、`success_consequence`、`failure_consequence`、`disabled_rule`、`return_rule`。

        8. 禁止出现“跳转相关页面”“执行对应操作”“根据情况处理”等模糊描述。所有行为必须落到确定的页面、Action、Branch、Overlay 或当前状态。

        9. 有多个执行路径的组件必须使用 `RESOLVE_BRANCH` 和 `branch_set_id`，并在 `structured_condition_branches` 中定义确定分支；无分支命中时使用 `BLOCK_AND_REPORT`。

        10. 每个 Screen 都必须有对应的 `page_lifecycle`，明确页面进入读取的数据、Query、Selector、必要参数以及卸载时资源清理。

        11. 所有 Dialog、Scanner、Preview 等必须进入 `overlay_registry`，并与触发 Component、确认 Action、成功/失败后果建立完整引用关系。模板若保留 Drawer 字段或动作类型，仅作兼容标识，实际展示使用居中弹窗或已有详情页面。

        12. 正式业务数据必须通过统一 Store 管理。页面只能维护 Draft/UI State，不能维护独立业务数据副本。

        13. 所有正式业务写操作必须进入 `action_registry`；涉及多个实体变化时必须建立原子 `transaction`，失败整体回滚。

        14. 根据目标业务重新设计 `data_model_contract`。例如实体应根据实际业务决定，不能机械照抄原模板实体。

        15. `selector_registry` 负责派生数据，`query_registry` 负责读取；页面不得自行维护重复统计结果。

        16. 如果目标是 **手机APP或windows应用**，保留模板中 `web_shell_component_contracts`、`web_layout_and_visual_requirements`、`browser_acceptance_contract` 等标签名称，但其内部交互和布局必须重新适配，不得机械保留桌面左侧导航、1440×900 等原 Web 规则。

        17. `core_modules`、`cross_module_processes`、`data_standards_and_integration`、`security_compliance_requirements`、`non_functional_requirements`、`acceptance_summary`、`interactive_ui_acceptance_criteria`、`reference_basis` 等模板章节全部保留并重新生成业务内容。

        18. 模拟数据必须真实合理，不使用“张三、李四、test、123456、图书1”等明显占位数据；同一实体跨页面信息必须一致。

        18.1 不设计右侧抽屉。需要详情、编辑或确认时，使用居中弹窗或已有详情页面，并完整定义打开、关闭、确认、取消和返回行为。
        18.2 screen_manifest 和组件契约不得要求在主内容区上方显示页面描述，也不得要求左上角说明性副标题。
        18.3 编号必须稳定唯一且符合业务格式，禁止以记录顺序生成连续尾号；时间不得按固定分钟、小时或天数递增，仍须满足业务先后关系。
        18.4 data_model_contract、selector_registry 和 query_registry 要明确实体 ID、跨页字段和统计口径。卡片、完整列表、筛选结果及分页总数必须能由同一实体集合推导。
        18.5 对含二维码的组件定义实际编码内容与实体的对应关系；二维码必须可解码，禁止仅用装饰图案表示扫码能力。
        18.6 页面数量较多时允许按业务模块使用二级导航；详情和编辑页通过业务入口进入，不自动成为一级菜单。
        18.7 表单内保存、提交、确认、取消、重置、添加、删除等按钮必须定义可验证的操作后状态，含适用的校验失败和成功状态。

        19. 生成结束前检查：

        * 所有 screen_id 唯一
        * 所有 route 唯一
        * 所有 target_screen_id 可解析
        * 所有 branch_set_id 可解析
        * 所有 dialog_id 可解析到 overlay
        * 所有 action_id 可解析
        * 所有 transaction_id 可解析
        * 所有 Selector/Query 引用的 Entity 存在
        * Screen 数量与 expected_screen_count 一致
        * Interaction 数量与 migrated_count 一致
        * 不存在实验室样品业务残留
        * XML 标签完整闭合

        20. **不得使用“省略”“同上”“其余类似”“...”来减少内容。**

        21. 组件行为差异化要求

            不得为了快速补全 screen_component_contracts，对不同业务组件机械复制相同的 preconditions、immediate_feedback、data_consequence、success_consequence、failure_consequence、disabled_rule 和 return_rule。

            每个组件的行为必须由其实际业务职责、实体状态、角色权限和上下文推导。

            对每个可操作组件，至少检查以下维度是否具有业务特异性：

            操作对象是什么；
            操作前需要校验什么状态；
            点击后立即改变哪个局部 UI；
            是否仅修改 Draft，还是修改正式业务 Entity；
            调用哪个 Query / Action / Branch；
            成功后具体改变哪些字段或实体；
            哪些 affected_screens 需要刷新；
            失败后需要保留哪些输入或原状态；
            哪些业务状态下必须禁用；
            返回后需要恢复什么上下文。

            如果两个组件上述行为完全相同，应优先判断它们是否实际上属于同一个可复用组件或同一个 Action，而不是复制两份相同契约。

            如果两个组件属于不同业务动作，则不得仅通过修改组件名称或 Toast 文案制造差异，必须在 Preconditions、Action、数据后果、状态变化、失败恢复或返回上下文中体现真实业务区别。

            允许真正通用的基础行为复用 FIELD_EDIT、QUERY、SUBMIT、CONFIRM_DIALOG、NAVIGATE、DISABLED，但这些模板只定义公共交互骨架；每个业务组件仍必须补充自己的业务条件和业务后果。

            最终生成后进行“组件行为重复检查”：对不同 component_id 的行为契约进行比较。如果多个非同族业务组件的行为描述高度相似，仅更换对象名称或页面名称，则重新推导这些组件行为后再输出。

        22. 禁止使用其他skill,尤其禁止使用superpowers、rtk
                             
        需求文档模版:
        {template}

        目标系统名称：
        {name}

        目标系统开发规范路径：
        docs/superpowers
        
        请完整解析模板后，基于模板生成 {os.path.join(save_dir,name+'_交互需求文档.xml')} 。
        最终只输出完整 XML 需求文档。
        ''').strip()

    cmd = [
        CLAUDE_BINARY,
        'exec',
        '-m', GET_REQUIREMENT_MODEL,
        '-c', f'model_reasoning_effort={GET_REQUIREMENT_MODEL_EFFECT}',
        '-C', CWD,
        '-c', 'project_root_markers=[]',
        '--dangerously-bypass-approvals-and-sandbox',
        prompt
    ]

    process = subprocess.Popen(
        cmd,
        cwd=save_dir,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,

    )

    for line in process.stdout:
        print(line, end="")

    process.wait()
            
     
def get_htmls(requirement_file, screenshots_dir, save_dir, cate='web'):
    os.makedirs(save_dir, exist_ok=True)
    assert cate in ['web','手机app','windows应用']
    shared_context_path = prepare_shared_context(requirement_file, save_dir)
    # validate_stage_outputs('shared_context', save_dir)

    PREFIX = textwrap.dedent(f'''
        你的任务是生成一个完整可运行的 HTML 页面。

        生成结果必须是单个 HTML 文件，包含 HTML、CSS、JavaScript。

        【布局与文字规范】
        主内容容器填满导航与顶栏之外的可用区域，页面主体使用合理网格或弹性布局，不得出现大块无效空白或通过增加假数据填空。
        主内容区上方禁止页面描述信息，左上角禁止说明性副标题；保留必要页面名称、字段提示和校验信息。
        当前页面使用共享显示规则中的字号、字重、行高和文字层级；同语义层级不得自行另定一套样式。
        表单正文、字段组、输入组件、错误提示和底部按钮区保持明确内边距与间距；文字、组件不得相互遮挡或被裁切。
        禁止右侧抽屉。需求中的 OPEN_DRAWER 或 drawer 展示改为居中弹窗或已有详情页面，并保留原确认、取消、校验和业务后果。


        【页面实现目标】

        生成的页面必须同时满足：
        1. 页面视觉风格接近参考截图；
        2. 当前页面所有组件均实现真实业务交互；
        3. 组件行为严格符合 requirement_file 中的 screen_contract 和 component_contract；
        4. 可以使用 Playwright 验证当前页面所有关键交互；
        5. 所有交互采用稳定 DOM 和局部更新，不得因状态变化产生整页闪烁、白屏、焦点丢失或地图重建。

        禁止：
        - 静态页面；
        - 点击无响应；
        - 点击只显示 toast；
        - 使用 alert 模拟业务完成；
        - 所有按钮使用相同反馈；
        - 存在可点击但无行为的组件；
        - 交互后重新生成整个页面；
        - 使用全量 innerHTML 作为通用状态渲染机制。
        - 使用ui-ux-pro-max


        【需求解析】

        生成代码前，必须从 requirement_file 中定位当前 screen_id，并解析：

        screen_id

        页面信息：
        - task_family
        - layout_type
        - primary_interaction_surface
        - ordered_functional_regions
        - navigation_pattern
        - action_placement
        - secondary_surface
        - detail_opening_mode

        然后解析当前页面所有 component_contract。

        每个组件必须读取并实现：
        - component_id
        - event
        - preconditions
        - action_type
        - target_screen_id
        - route_params
        - immediate_feedback
        - data_consequence
        - success_consequence
        - failure_consequence
        - disabled_rule
        - return_rule

        必须建立：

        component_id → event → action_type → handler → affected_regions

        affected_regions 表示本次交互允许更新的局部 UI 区域，例如：
        - commandDialog
        - targetDialog
        - mapMarkers
        - mapLayers
        - tableBody
        - pagination
        - loadingState
        - validationMessage
        - feedback

        每个 handler 必须明确 affected_regions，禁止无范围地重新渲染全部页面。
        禁止遗漏任何 component_id。


        【支持的事件类型】

        必须支持：
        - click
        - input
        - change
        - submit
        - draw_complete
        - socket_message
        - page_enter

        不同 event 必须有不同处理逻辑。

        input/change：
        修改页面状态或表单 draft，只同步关联字段、校验信息和按钮状态，不得重建整个表单或页面。

        submit：
        执行提交事务，只更新提交相关区域、Loading、错误信息和成功结果。

        draw_complete：
        更新地图绘制数据，只更新对应图形和关联信息。

        socket_message：
        更新实时数据状态，只更新发生变化的目标、轨迹、时间和连接状态。

        page_enter：
        初始化页面数据和稳定 DOM，完整页面初始化最多执行一次。


        【支持的动作类型】

        必须实现：
        - NAVIGATE
        - OPEN_DIALOG
        - OPEN_DRAWER
        - SWITCH_VIEW
        - SUBMIT
        - UPDATE_STATE
        - TOGGLE
        - MAP_INTERACTION
        - RESOLVE_BRANCH

        不同 action_type 必须产生不同业务行为。

        NAVIGATE：
        组件必须调用统一 navigate(screenId, routeParams) 接口，不得直接设置 window.location.href。
        独立页面运行时由导航适配器将 screenId 映射到文件地址；合并成 SPA 后由唯一 Router 接管同一接口。

        要求：
        1. 根据 target_screen_id 生成目标地址；
        2. 根据 route_params 传递参数；
        3. 目标页面可以不存在；
        4. 不需要实现其他页面。

        禁止点击后只显示“跳转成功”。

        OPEN_DIALOG：
        必须打开真实弹窗。

        弹窗必须包含：
        - 当前业务对象信息；
        - 确认按钮；
        - 取消按钮。

        确认后执行对应状态变化。
        取消不能修改业务数据。
        打开和关闭弹窗不得重建主页面、地图、表格、侧栏或当前表单。

        OPEN_DRAWER：
        作为兼容原需求的动作类型处理，不得生成右侧抽屉；改为居中 Dialog 或已有详情页面。

        需要：
        - 加载对应对象；
        - 显示上下文信息；
        - 支持关闭。

        打开和关闭目标界面只更新关联内容与选中状态，不得重新生成整个页面。

        UPDATE_STATE：
        必须修改页面状态。
        禁止只修改 DOM。

        错误：
        input.value = value;

        正确：
        GlobalStore.ui[screenId].formDraft.name = value;
        syncNameValidation();
        syncSubmitState();

        SWITCH_VIEW：
        必须改变当前页面视图状态，并仅更新目标视图区和激活状态。

        TOGGLE：
        必须改变对应开关、图层或显示状态，并只同步对应区域。

        MAP_INTERACTION：
        必须更新地图相关状态，并通过修改稳定地图节点的属性、class、transform、path 或坐标完成 UI 更新。

        RESOLVE_BRANCH：
        必须根据业务条件进入不同结果，并分别处理成功、失败和无权限分支。


        【页面状态管理】

        当前独立页面使用统一 GlobalStore 接口：正式实体保存在 entities；当前 screen_id 的草稿、筛选、Tab、Dialog、Loading 和错误状态保存在 ui[screenId]。
        独立页面可单独初始化这套接口，合并时只能保留一份 GlobalStore 实例和一份正式实体数据。
        禁止声明 pageStore、PageStore 或独立业务数据副本，也不得通过别名保留第二套 Store。
        组件交互先更新 GlobalStore 对应状态，再同步 affected_regions；禁止把状态变化实现为重新生成整个页面。
        禁止直接修改页面 DOM 作为唯一状态。


        【渲染架构与防闪烁要求（强制）】

        本节优先级高于其他渲染要求。

        页面必须采用“稳定页面骨架 + 局部状态同步”架构。

        页面的 body、#app、Header、主布局、地图、表格外壳和 Dialog 根节点必须在初始 HTML 中建立。首次加载后，这些节点必须保持 DOM 身份稳定。

        允许存在一次性的 initializePage() 或 renderInitialPage()，但只能在 page_enter 时执行一次。

        初始化完成后，必须使用局部同步函数，例如：
        - syncHeader()
        - syncMapMarkers()
        - syncMapLayers()
        - syncSelectedTarget()
        - syncCommandDialog()
        - syncDetailDialog()
        - syncTableBody()
        - syncPagination()
        - syncLoadingState()
        - syncValidation()
        - syncFeedback()

        推荐交互模式：

        GlobalStore.ui[screenId].dialogs.command = true;
        syncCommandDialog();
        syncFeedback();

        禁止为了打开 Dialog 而重新生成地图、侧栏、Header 或整个页面。


        【禁止全量 DOM 重建】

        用户交互、异步响应和实时消息发生后，禁止执行：

        - document.body.innerHTML = ...
        - document.documentElement.innerHTML = ...
        - app.innerHTML = ...
        - app.outerHTML = ...
        - app.replaceChildren(...)
        - root.innerHTML = renderPage()
        - 重新生成整个 main、workspace 或页面根节点
        - 先清空主页面再插入新内容
        - 每次状态变化后重新绑定页面全部事件

        以下实现属于错误实现：

        function render() {{
        document.getElementById("app").innerHTML =
            renderHeader() +
            renderMap() +
            renderSidebar() +
            renderDialog();
        }}

        所有 click、input、change、submit 和 socket_message 都调用上述 render()，同样属于错误实现。

        不得使用一个无更新范围的全局 render() 处理所有交互。

        如需根据数据生成列表，只允许替换最小动态区域，例如 tbody、列表结果容器或分页容器，不得替换页面根节点和稳定布局。

        事件监听必须：
        - 页面初始化时绑定一次；或
        - 使用稳定父节点进行事件委托。

        禁止每次 UI 更新后调用 bindAllEvents() 或重新绑定页面全部组件。


        【稳定 DOM 身份要求】

        页面首次初始化后，下列节点不得被销毁后重新创建：
        - body；
        - #app 或页面根节点；
        - Header；
        - main、workspace 等主布局；
        - 地图容器；
        - 地图 SVG 或 Canvas；
        - 表格外壳；
        - 当前获得焦点的 Input、Textarea、Select；
        - Dialog 根容器。

        局部状态更新不得导致上述节点失去 DOM 身份。


        【Dialog 局部更新】

        Dialog 必须使用稳定根节点，例如：
        - #dialog-root

        应在初始 HTML 中创建对应容器，通过以下方式控制：
        - hidden；
        - aria-hidden；
        - classList；
        - inert；
        - 更新局部文本和表单字段。

        打开 Dialog 时：
        1. 更新 GlobalStore.ui[screenId].dialogs；
        2. 更新 Dialog 内的业务对象信息；
        3. 显示 Dialog；
        4. 将焦点移动到 Dialog；
        5. 保持主页面和地图 DOM 不变。

        关闭 Dialog 时只隐藏 Dialog，不得重建主页面。

        允许替换 Dialog 内部的最小内容区域，但不得替换 #app、main、workspace、地图或侧栏。

        原需求中的 drawer 类内容也复用 Dialog 或详情页面，不创建侧边抽屉容器。


        【Input 与表单稳定性】

        input/change 事件发生时：
        1. 更新 GlobalStore.ui[screenId].formDraft；
        2. 只更新对应错误信息、字数、按钮禁用状态或关联字段；
        3. 不得重新创建当前 Input、Textarea 或 Select；
        4. 必须保持焦点、光标位置和用户已输入内容。

        禁止输入一个字符就重新渲染整个表单、Dialog 或页面。
        禁止在每次 input 事件后用 GlobalStore 中的值重新生成 textarea 或 input HTML。


        【组件真实反馈】

        每个交互必须包含：
        1. 用户操作反馈；
        2. 状态变化；
        3. 局部 UI 变化；
        4. 成功结果；
        5. 失败处理。

        例如 SUBMIT：

        点击：
        → 校验 preconditions
        → 更新对应 loading 状态
        → 禁止重复提交
        → 模拟请求
        → 仅同步提交按钮、目标表单和反馈区域

        成功：
        → 更新 GlobalStore
        → 局部刷新受影响数据
        → 显示成功状态

        失败：
        → 保留用户输入
        → 显示错误原因
        → 允许重新提交
        → 不得清空或重建整个页面


        【组件类型要求】

        根据需求文档识别真实组件类型，包括但不限于：
        - Button
        - Link
        - Input
        - Select
        - Dropdown
        - Tab
        - Table
        - Table Row
        - Pagination
        - Search
        - Filter
        - Card
        - Dialog
        - Dialog
        - Upload
        - Timeline
        - Map
        - Layer Control

        不同组件必须实现对应行为。


        【禁止交互同质化】

        禁止所有按钮都采用：

        点击 → toast("成功")

        必须区分：

        查询：
        刷新查询结果区域。

        详情：
        打开居中详情弹窗或通过统一导航接口进入详情页面。

        编辑：
        修改 draft 并同步关联字段。

        删除：
        打开确认 Dialog。

        导出：
        创建导出任务状态。

        审批：
        进入确认流程。

        地图：
        改变选中对象、标记状态和视图。


        【页面跳转】

        当前只生成一个页面。

        因此：
        - 不需要实现完整 SPA；
        - 不需要实现其他页面；
        - 需要沿用统一 GlobalStore 的结构和共享数据，避免合并时重复改造。

        但是：
        - 所有页面跳转调用统一 navigate(screenId, routeParams)；
        - 独立页适配器可将路由映射为目标 HTML 文件，合并后由 SPA Router 接管；
        - 不得在组件事件处理器中直接设置 window.location.href。


        【列表类页面】

        如果页面包含列表，必须实现：
        - 查询；
        - 筛选；
        - 分页；
        - 行选择；
        - 行点击；
        - Loading；
        - 空状态；
        - 错误状态。

        列表项点击必须携带对应业务 ID。

        查询、筛选和分页时必须保留：
        - 页面 Header；
        - Filter 表单；
        - Table 外壳；
        - 当前输入焦点。

        允许局部更新：
        - tbody；
        - 列表结果容器；
        - loading 区域；
        - empty/error 区域；
        - pagination；
        - 结果数量。

        不得清空整个页面或重新生成整个列表页面。


        【地图类页面】

        如果页面包含地图，必须模拟：
        - 地图区域；
        - 图层状态；
        - 标记点；
        - 当前选中对象；
        - 轨迹；
        - 详情弹窗联动。

        点击地图对象必须：
        - 更新 GlobalStore.ui[screenId]；
        - 更新对应标记点的选中状态；
        - 打开居中详情弹窗或详情页面；
        - 保持地图根节点不变。

        不能只显示静态图片。

        地图容器、SVG 或 Canvas 必须在 page_enter 后保持稳定。

        地图交互只能进行局部更新：
        - 选择目标：修改目标节点的 class、aria-selected 和选中状态；
        - 目标移动：修改 marker 的 transform、cx、cy 或对应坐标；
        - 轨迹变化：更新对应 path 的 d 或 points；
        - 图层开关：修改图层 group 的 hidden、class 或 visibility；
        - 地图缩放：修改稳定地图图层的 transform；
        - 打开详情弹窗：只更新 Dialog；
        - 打开指令弹窗：只更新 Dialog。

        禁止重新执行 renderMap() 后替换整个地图 HTML。

        实时 socket_message 到达时，只能更新发生变化的目标、轨迹、时间和状态，不得重建整个页面。


        【异步状态与视觉稳定性】

        进入 Loading 时：
        - 只更新当前操作按钮、目标区域或局部 Loading；
        - 不得隐藏整个页面；
        - 不得将主内容 opacity 设置为 0；
        - 不得先清空旧内容；
        - 不得使用白色空容器覆盖深色页面。

        如果需要替换局部内容，应先在 DocumentFragment 或离屏节点中准备完成，再一次性替换最小目标区域。

        页面背景必须从首次绘制开始保持一致，禁止因异步加载出现白屏或透明帧。


        【动画约束】

        允许 Dialog、Toast 使用短动画，但：
        - 不得给 #app、body、main、workspace 或地图根节点添加入场动画；
        - 禁止对页面根节点使用 transition: all；
        - 打开 Dialog 时底层页面不得重新执行入场动画；
        - 必须支持 prefers-reduced-motion；
        - 动画不得造成白屏、透明帧或布局尺寸归零。


        【Playwright验证】

        生成 HTML 后，必须使用 Playwright 验证当前页面。

        测试范围：
        当前 screen_id 所有 component_id。
        每个 component_id 至少测试一次。

        不能只测试：
        - 元素存在；
        - 按钮可点击。

        必须验证：
        - 触发行为；
        - GlobalStore 对应状态变化；
        - 局部 UI 变化；
        - 业务结果；
        - DOM 稳定性；
        - 焦点和输入稳定性；
        - 无整页闪烁。

        例如 component_id=M02-APPLICATIONS.CREATE：

        验证：
        - 点击按钮；
        - URL 变化；
        - target_screen_id 正确；
        - route_params 存在。

        例如 component_id=M03-LIVE.TARGET：

        验证：
        - 点击目标；
        - selected 对象变化；
        - 详情弹窗打开；
        - 地图根节点保持同一个 DOM 对象。

        例如 component_id=SUBMIT：

        验证：
        - Loading；
        - 禁止重复提交；
        - 成功状态；
        - 失败恢复；
        - 用户输入在失败后仍然存在；
        - 主页面没有被重建。


        【Playwright 防闪烁验证】

        对于 Dialog、筛选、分页、地图交互和表单输入：

        1. 操作前保存关键 DOM 节点引用；
        2. 执行交互；
        3. 验证操作后节点仍是同一个 DOM 对象；
        4. 验证节点没有被移除后重新创建；
        5. 验证主页面始终可见且尺寸不为 0。

        地图页面至少执行以下验证：

        window.__mapNode = document.querySelector("#map-canvas");
        window.__workspaceNode = document.querySelector(".workspace");

        点击目标、打开详情弹窗、点击“下发指令”后，必须满足：

        window.__mapNode === document.querySelector("#map-canvas")
        window.__workspaceNode === document.querySelector(".workspace")

        结果必须全部为 true。

        打开“下发指令”弹窗时必须验证：
        - Dialog 可见；
        - GlobalStore.ui[screenId].dialogs.command 为 true；
        - 地图节点未被替换；
        - workspace 节点未被替换；
        - 页面未发生跳转；
        - 主内容没有隐藏或清空。

        输入测试必须验证：
        - 连续输入多个字符；
        - GlobalStore.ui[screenId].formDraft 正确更新；
        - Input 或 Textarea 保持焦点；
        - DOM 节点没有被重新创建；
        - 光标位置没有跳回开头；
        - 已输入内容没有丢失。

        必须使用 MutationObserver 监控地图和页面主布局。

        关键交互期间，如果地图根节点、workspace 或主页面直接子节点被删除后重建，则测试必须失败。

        应在交互后的连续动画帧中验证：
        - #app 存在且可见；
        - main 或 workspace 存在且可见；
        - 地图容器存在且宽高大于 0；
        - 页面根节点 opacity 不为 0；
        - 页面根节点 visibility 不为 hidden；
        - 页面根节点 display 不为 none。

        如果发现以下实现，必须修改 HTML：
        - app.innerHTML 全量更新；
        - body.innerHTML 全量更新；
        - root.replaceChildren() 全量更新；
        - 打开 Dialog 时地图节点发生变化；
        - input 事件导致表单节点重建；
        - 每次交互重新绑定全部事件；
        - 主页面出现空白、透明或尺寸为 0 的帧。

        如果 Playwright 验证失败，必须修改 HTML 直到通过。
        
        【windows应用的纵向滚动条】
        只禁止页面最外层（html、body、根页面容器）出现纵向滚动条，即页面最右侧不得出现整体页面滚动轨道。

        要求：
        - 页面整体高度必须限制在视口高度内。
        - html、body、根容器禁止纵向滚动。
        - 页面内部的列表、表格、内容面板、侧边栏、弹窗等组件允许独立使用 overflow-y:auto 或 overflow-y:scroll。
        - 不允许全局隐藏所有滚动条。
        - 不得影响内部组件正常滚动。
        ''').strip()
    
    tasks = []
    screenshot_paths = sorted(Path(screenshots_dir).rglob('*.png'))
    if not screenshot_paths:
        raise RuntimeError(f'参考截图目录没有 PNG：{screenshots_dir}')
    expected_html = [path.with_suffix('.html').name for path in screenshot_paths]
    if len(expected_html) != len(set(expected_html)):
        raise RuntimeError('参考截图存在同名页面，无法唯一生成独立 HTML')
    
    for screenshot_path in screenshot_paths:
        
        prompt_path = screenshot_path.with_suffix('.txt')
        with open(prompt_path, 'r', encoding='utf-8') as fr:
            prompt = fr.read()
        prompt = prompt.replace('图片','html').replace('截图','html').replace('screenshot','html')

        temp_work_dir = os.path.join(save_dir, screenshot_path.stem)
        prompt = textwrap.dedent(f"""
                {PREFIX}
		
                【本阶段输入与约束】
                交互需求文档：{requirement_file}
                唯一共享数据及显示规则：{shared_context_path}
                参考截图附带的文字若写有“禁止参考其他文件”，那只适用于截图生成阶段；本阶段必须读取上述需求文档与共享数据。
                当前参考截图仅提供布局和视觉参考；若截图中的编号、时间、统计或二维码与共享数据冲突，以共享数据为准。
                不得为当前页面另造正式实体、统计常量或另一份业务 Store。
                页面正式实体均从共享数据按 ID 引用，卡片、表格和分页由同一数据集合与相同统计口径派生。
                编号稳定唯一且不按记录顺序连续递增；时间不得按固定分钟、小时或天数递增，并须符合业务先后关系。
                二维码必须由真实编码器生成，载荷来自对应实体的稳定业务内容；需能在离线 HTML 中解码，不得照抄参考图的装饰图案。
                如果存在表格，表格中至少20条默认数据
                
                参考截图：
                {str(screenshot_path)}
                你必须参考截图 {str(screenshot_path)} 的视觉效果，禁止使用image-to-code、superpowers。
                
                【最终输出】
                保存文件：
                {os.path.join(temp_work_dir, screenshot_path.with_suffix('.html').name)}

                最终页面必须满足：
                - 所有 component_id 已实现；
                - 所有 event 已处理；
                - 所有 action_type 已支持；
                - 页面内交互真实有效；
                - 页面跳转通过 navigate(screenId, routeParams) 接口执行；
                - 不存在无行为组件；
                - Playwright 验证通过。
                - 如果是手机app，app视图的尺寸为848*1618


                最终目标：
                生成一个可交互、可测试、符合业务契约的单页面 {cate} 原型，而不是静态截图。

                根本任务：
                根据 UI 交互需求文档 {requirement_file} 和 {shared_context_path}实现当前页面，而不是生成静态展示页面。

                输入：
                {prompt}
                如果上述输入内容和 {shared_context_path} 中的内容冲突，必须以 {shared_context_path} 为准
                
                如果任务失败，需要你将失败的详细信息 追加到 get_html_error.txt中
            """).strip()
   
        tasks.append((prompt, temp_work_dir, GET_HTML_MODEL, GET_HTML_MODEL_EFFECT))  
    
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(run_codex, prompt, workdir, model, reasoning_effort)
            for prompt, workdir, model, reasoning_effort in tasks
        ]

        for future in as_completed(futures):
            result = future.result()
    for name in expected_html:
        page = Path(save_dir) / Path(name).stem / name
        # if not page.is_file() or not page.stat().st_size:
            # raise RuntimeError(f'独立 HTML 缺失或为空：{page}')
            
        try:
            shutil.move(page, Path(save_dir) / name)
            shutil.rmtree(Path(save_dir) / Path(name).stem)
        except:
            print(f'移动 {str(page)} 报错')

    # validate_stage_outputs('html', save_dir)

def _validate_screenshot_interactions(html_path, required_component_ids):
    """拒绝缺少组件覆盖、未执行用例或对应旧 HTML 的交互验收结果。"""
    html_path = Path(html_path)
    report_path = html_path.parent / 'interaction_acceptance.json'
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f'缺少或无法解析交互验收结果：{report_path}') from exc
    if not isinstance(report, dict):
        raise RuntimeError(f'交互验收结果必须为对象：{report_path}')
    if report.get('html_sha256') != hashlib.sha256(html_path.read_bytes()).hexdigest():
        raise RuntimeError(f'交互验收 HTML 摘要不匹配，修改后必须重新测试：{html_path}')
    if report.get('status') != 'PASS' or any(
            type(report.get(key)) is not int or report[key] != 0
            for key in ('failed', 'blocked', 'not_tested')):
        raise RuntimeError(f'交互验收未通过：{report_path}')
    inventory, cases = report.get('inventory'), report.get('cases')
    if not isinstance(inventory, list) or not inventory or not isinstance(cases, list) or not cases:
        raise RuntimeError(f'交互验收缺少组件清单或测试用例：{report_path}')
    by_component = {}
    for item in inventory:
        if not isinstance(item, dict):
            raise RuntimeError('交互验收组件条目必须为对象')
        component_id, case_ids = item.get('component_id'), item.get('required_case_ids')
        if not isinstance(component_id, str) or not component_id.strip() or component_id in by_component:
            raise RuntimeError('交互验收组件 ID 为空或重复')
        if (not isinstance(case_ids, list) or not case_ids
                or any(not isinstance(value, str) or not value.strip() for value in case_ids)
                or len(case_ids) != len(set(case_ids))):
            raise RuntimeError(f'组件缺少有效的必测用例清单：{component_id}')
        by_component[component_id] = set(case_ids)
    missing = set(required_component_ids) - set(by_component)
    if missing:
        raise RuntimeError(f'交互验收遗漏需求组件：{sorted(missing)}')
    tested = {}
    for case in cases:
        if not isinstance(case, dict):
            raise RuntimeError('交互验收用例必须为对象')
        case_id, component_id = case.get('case_id'), case.get('component_id')
        if not isinstance(case_id, str) or not case_id.strip() or case_id in tested:
            raise RuntimeError('交互验收用例 ID 为空或重复')
        if not isinstance(component_id, str) or component_id not in by_component:
            raise RuntimeError(f'用例引用未登记组件：{case_id}')
        if case.get('status') != 'PASS':
            raise RuntimeError(f'交互验收用例未通过：{case_id}')
        for key in ('steps', 'assertions'):
            values = case.get(key)
            if (not isinstance(values, list) or not values
                    or any(not isinstance(value, str) or not value.strip() for value in values)):
                raise RuntimeError(f'用例缺少执行步骤或结果断言：{case_id}')
        tested[case_id] = component_id
    for component_id, case_ids in by_component.items():
        if any(tested.get(case_id) != component_id for case_id in case_ids):
            raise RuntimeError(f'组件存在遗漏或归属不符的必测用例：{component_id}')


def get_htmls_from_screenshot(requirement_file, screenshots_dir, save_dir, cate='web'):
    """以截图为视觉基准生成单文件 HTML，需求补行为，共享数据补业务值。"""
    if cate not in ('web', '手机app', 'windows应用'):
        raise ValueError(f'不支持的界面类型：{cate}')
    requirement_path = Path(requirement_file).resolve()
    screenshot_root = Path(screenshots_dir).resolve()
    output_dir = Path(save_dir).resolve()
    screenshot_paths = sorted(screenshot_root.rglob('*.png'))
    if not screenshot_paths:
        raise RuntimeError(f'参考截图目录没有 PNG：{screenshots_dir}')
    names = [path.with_suffix('.html').name for path in screenshot_paths]
    if len(names) != len(set(names)):
        raise RuntimeError('参考截图存在同名页面，无法唯一生成独立 HTML')
    requirement_root = ET.parse(requirement_path).getroot()
    page_contracts = {}
    for screenshot_path in screenshot_paths:
        screens = [screen for screen in requirement_root.findall('.//screen_manifest/screen')
                   if screen.get('html_file') == screenshot_path.with_suffix('.html').name]
        if not screens:
            screens = [screen for screen in requirement_root.findall('.//screen_manifest/screen')
                       if screen.get('page_name') == screenshot_path.stem]
        if len(screens) != 1 or not screens[0].get('screen_id'):
            raise RuntimeError(f'参考截图无法唯一映射到 screen_manifest：{screenshot_path.name}')
        screen_id = screens[0].get('screen_id')
        component_ids = {
            component.get('component_id')
            for contract in requirement_root.findall('.//screen_contract')
            if contract.get('screen_id') == screen_id
            for component in contract.iter()
            if component.get('component_id')
        }
        page_contracts[screenshot_path] = (screen_id, component_ids)
    output_dir.mkdir(parents=True, exist_ok=True)
    shared_context_path = os.path.join(output_dir,'shared_context.json') #prepare_shared_context(requirement_path, output_dir)

    prefix = textwrap.dedent(f"""
        任务：根据参考截图高保真复刻一个可交互的 {cate} HTML 页面。
        最终交付单个 HTML，内含 CSS、JavaScript、业务数据及所需图片素材。

        【三类输入的职责与冲突处理】
        1. 参考截图决定视觉：布局、区域顺序、位置、尺寸、间距、留白、颜色、字体效果、
           文字层级、行高、边框、圆角、阴影、图片内容、图标及初始可见状态。
           目标是逐项对齐截图，不是风格相近，不得自行美化、重新设计或套用通用模板。
        2. UI 交互需求文档决定功能：事件、校验、跳转、状态变化、业务流程及成功/失败分支。
           在截图已有组件上补齐行为，不得为了实现功能擅自重排初始页面。
           截图只描述一个可见状态，不是功能范围上限。初始视觉还原和全组件功能完整必须同时满足，
           不得以“截图没展示”“不是默认状态”“保持视觉”为由省略其他状态、内容或组件行为。
        3. 共享数据决定业务值：实体、ID、编号、时间、状态、统计、二维码载荷及跨页引用。
           数据格式与业务规则仍遵循共享数据。时间须满足：{TIME_RANGE}。
        4. 截图文字或数字与共享数据冲突时，使用真实共享业务值，保留原有容器与文字层级。
           不得伪造数据来匹配截图，也不得修改共享文件迁就视觉。记录因此产生的可见差异。
           必须显示完整的业务字段不得通过缩小整页或随意裁切掩盖；遵循字段规则处理换行或省略。
        5. 截图未展示的弹窗、抽屉、详情、加载、空状态、错误及禁用状态按需求补齐，
           沿用截图设计语言，仅在相应交互触发时出现。截图已有的抽屉或弹窗必须按图保留。
           需求必需但截图缺失的常驻入口，优先复用现有入口；必须新增时最小化布局影响并记录。
        6. 附带的截图生成提示词只是辅助背景，不能覆盖以上职责；其中“禁止参考其他文件”、
           “直接生成图片”等截图生成阶段命令不适用于本阶段。不得机械地把“图片”替换成“HTML”。

        【先观察，再实现】
        必须实际打开参考截图，读取原始宽高，不能只根据文件名和文字猜页面。
        以文件名/page_name 在 screen_manifest 中定位当前 screen_id；无法唯一定位时报告失败，禁止猜测。
        测量主要区域的边界、间距、颜色、字号、行高、图片显示范围及列表可见行数。
        以原图宽高作为基准 viewport CSS px，deviceScaleFactor=1，不额外套手机壳、系统状态栏或导航。
        不强制使用通用的 1440×900 或 848×1618；不得拉伸原图、缩放整个页面或修改对比图尺寸来掩盖误差。
        如果输入是长页面截图而非视口截图，依据明确的采集信息设置 viewport 与 full_page 并记录；
        缺少采集信息时采用原图尺寸作为基准并说明假设。
        编码前先完成下述全组件及状态清单，再建立截图对应的真实 DOM、业务状态和事件处理。
        初始视觉校准后继续完成全部可达状态；默认页面可点击不是完成标准。

        【全组件盘点与功能闭环：先列清单再编码】
        功能范围取以下并集，而非只看截图或只看 component_contract：截图中所有组件、当前页面全部需求契约、
        页面文字描述/全局行为模板/业务动作与查询/分支规则、当前页面可达的隐藏视图与浮层内组件。
        必须递归展开菜单、弹窗、抽屉、详情、向导、折叠区、非默认视图及其内部组件，直到没有未展开的交互入口。
        读取被引用的 dialog_id、branch_set_id、action/query、实体结构、权限与返回规则，不能只读组件名称。
        保存 component_inventory.json；每项记录 component_id、来源、父级/所在状态、类型、定位方式、
        数据绑定、事件、前置条件、状态转换、反馈、数据后果、成功/失败/取消/禁用/返回行为及 required_case_ids。
        文档已有 ID 必须沿用。截图或隐藏状态中有组件但契约未单列时，使用 screen_id.LOCAL.语义名补充稳定 ID，
        根据业务上下文实现合理且最小的完整行为，并记录推断；不得忽略，也不得擅自增加无关功能。
        行操作、重复卡片等可以按组件类型登记一次，但必须测试不同实体 ID、不同状态和事件委托，不能仅首行可用。
        纯文本、图片、统计卡等只读组件也登记数据来源、展示及联动刷新断言；不为纯装饰元素强加点击行为。
        缺少关键业务语义且无法合理推断时记为 BLOCKED，说明缺失条件，禁止用空函数或假成功补位。

        【需求追溯与状态内容定义：必须在页面编码前完成】
        对每个组件沿需求引用展开 event/action_id、query、selector、实体字段、overlay、branch、权限、
        生命周期与返回快照，形成“原始需求 → 状态内容规则 → 实现 → 用例”的可追溯关系。
        文档已经定义的内容、动作、分支与字段必须逐条落实，不得用截图布局或自行推断覆盖明确需求。
        文档只列出组件名称或动作而未明确内容范围时，不能认为已具备完整规格；先补齐内容与显隐规则。
        将结果保存为 state_content_contract.json，至少包含 screen_id、initial_state、state_variables、
        regions、states、transitions；用这份规则驱动实现和测试，不得先写页面再反过来描述现有代码为需求。
        state_variables 列出实际视图、模式、选中对象、展开项、权限、提交状态等变量及合法取值。
        每个 region 记录唯一 region_id、关联 component_ids、owner_state/共享范围、visible_when、
        数据绑定与筛选、应展示的字段/控件、需求来源 source_refs 或补充推断 inference_reason。
        每个 state 记录 state_id、进入前置条件、应显示的 visible_regions、应隐藏的 hidden_regions、
        必须呈现的内容、可执行/禁用的操作、数据作用域与恢复规则。
        每个 transition 记录触发组件与事件、起止状态、局部更新区域、成功/失败/取消后果和 required_case_ids。
        状态要覆盖所有可选值、业务分支和实际可达组合；不得只登记当前截图状态或穷举无业务意义的组合。
        规则来源分清三类：需求文档明确规定、截图只证明初始状态、结合组件语义和业务数据补充推断。
        对未明确内容，依据实体关系与操作语义补齐最小合理规则并记录依据；关键语义无法推断时记 BLOCKED。

        【公共区域与状态专属区域】
        截图中同时出现的多个区域，只证明它们在截图对应状态可见，不能据此推断它们在所有状态都可见。
        公共区域必须有需求依据或明确且合理的共享范围；不得把当前状态的列表、表单、历史、图表或详情
        直接放进永久显示的页面骨架，并在切换时只更新其中一小块。
        一个区域属于某视图/模式/对象时，只在 visible_when 成立时展示；退出时隐藏或清理对应内容，
        恢复时按契约读取正确的数据和草稿；不能保留上一状态无关的标题、记录、选择或可操作控件。
        数据由当前实体 ID、当前状态和实际筛选共同决定，不能仅按实体 ID 读取全部关联记录后处处显示。
        对 Tab/分段/模式等状态选择器，逐个定义其主内容、辅助内容、公共内容及禁止残留内容。
        对菜单、折叠、弹窗、向导、选择对象、权限与加载/错误等条件组件，同样明确区域归属及可见条件。
        若初始截图包含某状态的辅助区域，保留该状态的视觉，其他状态是否保留仍按各自规则确定。
        同一状态下同一明细集合原则上只呈现一次；需求明确要求摘要与详情并存时分别实现，
        不能将常驻区内容再复制进切换区，产生重复标题、重复记录和重复操作入口。
        稳定 DOM 是保留容器身份，不是永久展示其内容；允许通过 hidden/class/局部内容同步实现状态显隐。
        隐藏区域不得继续占据无意义空白、接收焦点或触发操作；禁用区域按契约保留可见状态与原因。

        【所有组件统一的实现标准】
        每个交互都必须完成：用户操作 → 前置校验 → 状态/事务变化 → 真实结果 → 关联区域同步 → 后续操作/返回。
        为组件全部合法取值、选项、分支、模式及子状态实现内容和行为，不能只实现当前选中项或一个成功分支。
        根据适用性覆盖初始、进行中、成功、失败、空结果、禁用/无权限、取消、重试、返回和重复操作；
        不适用的分支明确说明原因，不得统一标为不适用以跳过实现。
        事件绑定、选中样式变化、控制台日志、toast 或打开空容器均不足以证明功能完成。
        组件完成的依据是可观察的业务结果，以及 Store、列表、详情、统计和相关组件之间一致的数据变化。
        离线 HTML 可使用基于共享数据的本地业务服务模拟查询和事务，并提供可测试的失败路径；
        必须真正筛选、计算、更新、生成文件或改变状态，不能永远返回成功。不得为了测试修改正式共享输入文件。
        测试所需临时实体/状态放隔离测试副本，测试后恢复初始数据，不把测试用例写进正式页面展示。

        【按实际组件类型补齐行为，以下是示例而非范围上限】
        - 导航、菜单、面包屑、链接、返回：目标、参数、权限、历史、来源状态恢复及失败处理完整。
          同页视图必须真实显示；跨页目标由其他页面实现，独立阶段验证导航协议，合并阶段验证到达与返回，
          不得把只验证路由参数写成跨页流程已通过。
        - Tab、分段、模式切换、折叠、树：所有可选项都可操作并显示对应真实内容/数据，内部组件继续可用；
          切换状态写入 Store，关联筛选/计数刷新；往返切换按契约保留或重置草稿、选择、分页与滚动。
          不得所有面板复制相同内容，不得以空白或“建设中”替代未激活面板；无数据时显示真实空状态及适当操作。
        - 输入、下拉、搜索、日期/范围、单复选、开关、滑块、上传等：全部选项、清空、约束、联动、边界和键盘操作有效。
          表单包含初始化/编辑回填、草稿、必填/格式/范围/跨字段校验、字段错误、提交锁、保存事务、失败保留、取消/重置。
          成功后列表、详情与统计反映新值，重新打开可读取已保存值；取消不得落库，重复提交不得生成重复记录。
        - 按钮、图标按钮、快捷操作：按各自业务执行新增、编辑、复制、删除、审批等事务及确认/取消/失败恢复，
          不得把不同操作统一绑定同一个反馈函数。
        - 表格、列表、卡片集合、树形数据：查询、筛选、排序、分页、选择、全选/半选、批量与行操作按实际需求实现，
          数据、总数、选中集合及翻页结果一致；覆盖非首项、空结果、边界页与操作后刷新。
        - 弹窗、抽屉、Popover、上下文菜单：入口、内容、内部全部控件、确认、取消、关闭、焦点及再次打开完整；
          按规则处理遮罩/Escape/提交中关闭，不得只做“打开和关闭”而遗漏内部业务。
        - 步骤条、向导、流程、拖拽/排序/绘制：每步/每分支可达，前置条件与前进/后退有效，草稿与最终结果一致。
        - 文件导入/上传/导出/下载/预览：选择、格式/大小校验、解析/进度、错误、删除/重试及最终内容有效；
          导出真实文件且内容来自当前数据范围，不能只出现“下载成功”。
        - 图表、地图、时间轴、媒体、二维码等专用组件：按契约实现选择、缩放、图层、图例、钻取、时间范围、
          播放/定位/解码等实际存在的操作，关联数据与视图同步；不可用一张静态图替代要求可操作的对象。
        - 其他未列出的组件：同样按输入、事件、状态转换、业务输出、异常、联动和返回规则完整实现并验证。
        只实现本页面及其附属状态实际存在或需求明确要求的组件，不为凑分类凭空新增组件。

        【布局与文字】
        保留截图中的留白、内容密度、区域比例、标题、说明文字和滚动方式。
        不得强制填满空白、增加装饰卡片、删除截图已有标题、统一改字号或更换布局。
        不得为凑足 20 条记录另造实体；共享数据的总量与截图可见行数是两个概念。
        使用截图中的行高、容器高度和分页/滚动机制展示共享数据，总数和分页须由同一集合计算。
        文字使用真实文本节点；优先匹配可用字体，中文使用简体字形，记录缺失字体造成的差异。
        非基准视口下允许合理自适应，但不能以响应式重排为理由改变基准视口的布局。

        【照片与复杂素材：必须复用像素内容】
        动物、人物、植物、商品实拍、风景、复杂插画、纹理和装饰背景属于图片素材。
        优先使用输入明确提供且与截图一致的原始素材；没有原素材时，从当前截图裁剪对应区域。
        禁止用 emoji、近似网络图片、重新生成的图片、CSS/SVG 绘画或占位色块代替参考照片。
        简单图标可用 SVG/CSS 实现，但须匹配截图轮廓、尺寸和笔画，不得用它们重画实拍内容。
        裁剪前记录原图宽高及原始像素坐标 x、y、width、height；若根据缩放预览定位，必须映射回原图。
        使用本地裁剪脚本实际提取像素，不得让语言模型凭空编写图片字节；裁剪坐标必须在原图范围内。
        裁剪照片显示区域并保留照片自身背景，排除外围卡片、标题、按钮、边框和阴影。
        查看每张裁剪结果确认边界；圆角、边框、阴影由 CSS 实现，避免把截图底色的圆角边缘当照片。
        图中文字或按钮遮挡照片时，先查找明确提供的干净原素材；缺失时记录不可恢复区域，
        不得声称能从截图恢复被遮挡像素、不得重复叠加相同文字，也不得擅自生成内容冒充原素材。
        图片通过 img 或 background-image 展示，保持宽高比及截图中的构图，按需设置 object-fit/object-position。
        不得把整页、完整卡片、表单、表格或其他交互区域裁成图片代替 DOM；不得把整页截图铺底后覆盖透明按钮。
        地图可使用合适的底图素材，但交互标记、图层、轨迹和控件必须独立实现。

        【单文件与素材保存】
        中间素材、裁剪清单、测试脚本和对比图可放在当前工作目录。
        最终 HTML 的图片必须由程序读取实际文件字节，编码为带正确 MIME 的 Base64 data URL 后嵌入；
        禁止手写或转抄大段 Base64。不要把大量图片编码输出到日志。
        共享数据也须内嵌初始化，不能依赖运行时 fetch 本地 JSON；CSS/JS 不依赖 CDN。
        最终 HTML 会被移动至输出目录根部，不能引用临时目录、绝对本地路径或其他外部素材文件。
        确认全部图片解码成功；单文件体积过大时先报告，不得擅自降低照片质量。

        【业务契约与统一状态】
        读取当前 screen_contract 和全部 component_contract，逐项解析 component_id、event、
        preconditions、action_type、target_screen_id、route_params、immediate_feedback、data_consequence、
        success_consequence、failure_consequence、disabled_rule、return_rule。
        建立 component_id → 所在视图/状态 → event → handler → affected_regions → 验收用例 的可检查映射。
        当前页面范围包含全部非默认面板、内嵌详情、浮层与内部组件，不能只实现截图拍摄时的状态。
        不额外生成属于其他 screen_id 的页面，但必须实现本页到目标的导航协议及失败反馈。
        使用 GlobalStore：正式实体放 entities；草稿、筛选、Tab、弹窗、Loading 和错误放 ui[screenId]。
        正式实体按共享 ID 引用；统计按共享 filters/aggregation 计算；不得创建另一套 Store 或矛盾副本。
        状态变化先更新 Store，再更新受影响的局部区域，不能只改 DOM 冒充业务状态。
        页面导航统一调用 navigate(screenId, routeParams)，独立页适配器按 manifest 映射目标文件，
        合并后可由唯一 Router 接管；事件处理器不得散落直接 window.location 跳转。
        根据契约实现 click/input/change/submit/draw_complete/socket_message/page_enter 等实际声明的事件，
        以及 NAVIGATE/OPEN_DIALOG/OPEN_DRAWER/SWITCH_VIEW/SUBMIT/UPDATE_STATE/TOGGLE/MAP_INTERACTION/RESOLVE_BRANCH。
        需求未逐条列出但截图/可达状态中存在的组件仍须按全组件清单实现。确认执行事务，取消不修改正式实体；
        错误、禁用、无权限分支须有效。
        禁止所有按钮只弹 toast、使用 alert 模拟完成或只改按钮文字；导出、筛选、分页等须有实际结果。
        二维码若存在，必须用真实编码器按共享业务载荷生成并验证可解码，不能裁剪装饰二维码替代。

        【稳定渲染】
        初次建立的页面根节点、主布局、地图、表格外壳、当前表单及弹窗根节点保持 DOM 身份稳定。
        初始化后禁止全量重写 body/app/main 的 innerHTML、outerHTML 或 replaceChildren。
        只更新 affected_regions；监听器初始化绑定一次或采用事件委托。
        打开弹窗、输入、筛选、提交和实时更新不得整页闪烁、丢焦点或重置地图与滚动位置。

        【必须执行的验证顺序】
        1. 先在基准 viewport 下截图；等待字体 ready、img 解码和 CSS 背景图片加载完成及页面稳定。
           临时测试时关闭动画、固定测试时间或随机因素，但不得破坏实际功能。
        2. 保存参考图与渲染图的并排/叠加或差异图，检查布局、边界、间距、文字、照片构图及可见行数。
           修正非数据原因造成的差异；不能只凭“风格相似”判定完成。
        3. 通过 Playwright 逐项执行 component_inventory.json 中所有组件的必测用例，不得只抽查关键按钮。
           用例必须从 state_content_contract.json 的规则派生，不得只根据生成后的 DOM 选取容易通过的断言。
           从页面入口实际操作进入每个隐藏状态，再操作其内部组件；不能直接改 Store 或调用 handler 代替用户操作。
           测试前可在隔离环境布置权限、网络失败、边界数据等前置条件，断言实际 UI 结果和数据后果。
           每个组件必须验证内容/结果，而非仅验证 click 不报错；只读组件验证展示与数据联动。
           对每个可达状态同时验证：应显示的区域/字段/数据/操作存在且正确；应隐藏的区域不可见且不可操作；
           数据不属于当前实体或当前状态时不能混入；无上一状态残留；无重复明细；公共区域按登记范围保留。
           检查作用范围应包含整个业务内容区及相关浮层，不能只查被更新的单一容器而漏掉旁边的常驻内容。
           对切换/返回/取消/重试等转换，既验证目标状态，也验证来源专属内容的退出与恢复、草稿及焦点规则。
           显隐测试使用实际可见性和操作可达性断言；隐藏节点保留文本可以接受，不能仅凭源码包含文字判断显示。
           状态确实没有互斥区域时，在状态规则中记录理由并验证公共范围，不能机械地要求所有组件都互相隐藏。
           覆盖全部合法选项/分支、成功、失败、取消、禁用、返回及重复操作；不适用项在清单中说明依据。
           记录每例的组件 ID、入口状态、操作步骤、预期断言、实际结果和 PASS/FAIL/BLOCKED/NOT_TESTED。
           检查控制台异常、图片加载、页面根节点稳定性和输入焦点；禁止仅做静态源码检查。
           保留可重跑的 Playwright 脚本和执行日志，发现失败则修复并重跑关联用例，最终执行完整回归。
        4. 恢复初始业务状态，再次截图对比，确认补齐功能没有改变初始视觉布局。
        5. 将视觉核对、交互结果、素材来源/裁剪坐标以及数据替换、遮挡、缺失字体等差异写入当前目录
           reproduction_report.md。区分已修复、必要的数据差异及仍未解决的问题；未实际验证不得写通过。
        6. 交付前检查 HTML 移动后仍可独立显示与交互；不存在外部图片路径、缺失组件或无行为按钮。
        7. 保存 interaction_acceptance.json，作为交付前必须通过的机器验收结果：
           顶层 html_sha256 为最终 HTML 文件真实字节的 SHA-256，由程序计算，修改 HTML 后必须重跑验证并更新摘要；
           status 为 PASS/FAIL/BLOCKED，failed、blocked、not_tested 为实际未通过用例数量（整数）；
           inventory 为完整组件数组，每项含 component_id 和非空 required_case_ids 字符串数组，
           必须覆盖本阶段输入列出的所有需求组件，也包括补充识别出的组件；不得在验收时删减前置功能清单；
           cases 为实际执行的用例数组，每项含唯一 case_id、component_id、status、非空 steps 与 assertions 字符串数组。
           每个状态转换用例还记录 source_state、target_state、涉及 region_ids；assertions 明确写出验证过的
           内容正确性、显示/隐藏、数据作用域、残留清理与必要的禁止操作结果，不得只写“切换成功”。
           inventory 的 required_case_ids 必须包含状态内容规则中适用的所有转换与显隐用例，
           需求追溯、组件清单、状态规则、实际测试四者保持一致，不能用重复的泛化用例冒充不同状态覆盖。
           每项必测用例必须存在、归属正确且 PASS；steps 写实际浏览器操作，assertions 写实际验证过的结果，
           禁止编造执行记录。没有浏览器或依赖缺失导致不能测试，必须记 BLOCKED，不得按源码推测通过。
           纯只读页面也须为展示组件执行数据与呈现用例，不能交空清单。
           只有视觉核对完成、所有组件和必测用例通过且 failed=blocked=not_tested=0 才允许 status=PASS。
           外部服务与其他页面的端到端测试边界另写 reproduction_report.md，不得宣称当前阶段已经覆盖。
        只依据本阶段输入执行，不使用会重设计页面的 skill，不参考其他项目。
    """).strip()

    tasks = []
    for screenshot_path in screenshot_paths:
        # if '个体详情'  in screenshot_path.stem:
            # continue
        prompt_path = screenshot_path.with_suffix('.txt')
        source_prompt = (prompt_path.read_text(encoding='utf-8')
                         if prompt_path.is_file() else '未提供附带提示词，以截图和需求文档为准。')
        workdir = output_dir / screenshot_path.stem
        html_path = workdir / screenshot_path.with_suffix('.html').name
        screen_id, required_component_ids = page_contracts[screenshot_path]
        prompt = textwrap.dedent(f"""
            {prefix}

            【本阶段输入】
            UI 交互需求文档：{requirement_path}
            唯一共享数据：{shared_context_path}
            参考截图：{screenshot_path}
            当前页面名称：{screenshot_path.stem}
            当前 screen_id：{screen_id}
            必须覆盖的需求组件 ID：{json.dumps(sorted(required_component_ids), ensure_ascii=False)}
            上述 ID 是最低覆盖范围；还必须盘点截图、全局规则及可达隐藏状态中的全部组件。
            当前工作目录：{workdir}
            最终 HTML 保存路径：{html_path}
            HTML 移动后的目录：{output_dir}

            【截图生成阶段的附带说明，仅作背景】
            {source_prompt}
            【附带说明结束】 

            再次确认：截图约束视觉，需求文档约束行为，共享数据约束业务值。
            先盘点全组件和全部状态，再复刻截图并完成所有行为，最后逐组件验证视觉、业务结果和状态联动。
            编码前完成 state_content_contract.json；明确每个区域属于哪些状态，以及何时显示、隐藏和更新。
            当前截图可见内容不能自动判为全状态公共内容；验收必须包含整个内容区的出现与隐藏检查。
            只完成默认视图、只绑定事件或只验证部分组件，均视为失败，不得交付。
            若失败，保留已生成的证据，并将具体原因写入当前工作目录的 get_html_error.txt。
        """).strip()
        tasks.append((prompt, workdir, html_path, required_component_ids))

    with ThreadPoolExecutor(max_workers=3) as executor: 
        futures = [executor.submit(run_codex, prompt, str(workdir), GET_HTML_MODEL, GET_HTML_MODEL_EFFECT)
                   for prompt, workdir, _, _ in tasks]
        for future in as_completed(futures):
            future.result()

    # 全部检查后再移动；保留页面目录中的裁剪清单、对比图与验收报告供复核。
    #for _, _, html_path, required_component_ids in tasks:
        #if not html_path.is_file() or not html_path.stat().st_size:
            #raise RuntimeError(f'独立 HTML 缺失或为空：{html_path}')
        # _validate_screenshot_interactions(html_path, required_component_ids)
    # for _, _, html_path, _ in tasks:
        # shutil.move(str(html_path), str(output_dir / html_path.name))


def merge_htmls(requirement_file, html_dir,cate='web',tool='codex'):
    work_dir = os.getcwd()
    shared_context_path = os.path.join(html_dir,'shared_context.json') #prepare_shared_context(requirement_file, html_dir)
    # validate_stage_outputs('shared_context', html_dir)
    # validate_stage_outputs('html', html_dir)
    manifest = ET.parse(requirement_file).getroot().find('.//screen_manifest')
    if manifest is None:
        raise RuntimeError('交互需求文档缺少 screen_manifest')
    source_htmls = []
    for screen in manifest.findall('screen'):
        name = screen.get('html_file')
        if name and Path(name).name == name and name not in ('merge.html', 'merge_bk.html'):
            source = Path(html_dir) / name
            source = Path(html_dir) / Path(name).stem / name

            if source.is_file() and source.stat().st_size:
                source_htmls.append(str(source.resolve()))
    if not source_htmls:
        raise RuntimeError('screen_manifest 中没有可合并的独立 HTML')
    source_file_list = '\n'.join(source_htmls)

    PROMPT = textwrap.dedent(f"""
        任务：你是资深前端架构师和前端工程师。根据固定格式的交互需求文档，将 多个已经独立实现完成的 HTML 页面整合为一个完整 SPA：


        ## 一、访问限制

        * 禁止使用任何 Skill。
        * 禁止访问网络。
        * 禁止新增外部依赖。
        * 最终业务页面只生成 `merge.html`；允许在 HTML 目录生成本次 Playwright 测试及验收证据。

        ## 二、核心原则

        ### 1. 本任务是“系统整合”，不是“重新实现页面”

        各独立 HTML 中现有组件均视为已经实现完整。
        **所有页面必须使用同一个 GlobalStore，merge.html 中不得存在 pageStore 或 PageStore。**
        **最后完整的SPA html中只存放代码，禁止将 交互需求文档的 描述性内容放入html中**

        如果现有行为与需求文档不存在明确冲突，必须保留：

        * DOM 与 CSS
        * 原事件处理
        * 字段联动
        * 表单校验
        * Loading / Disabled / Error
        * Dialog / Drawer / Popover
        * Tab / 搜索 / 筛选 / 排序 / 分页
        * 地图和其他局部交互
        * 焦点、键盘和局部 UI 状态

        禁止无必要重新生成、重写、简化或替换已有组件。

        只有现有行为与需求文档明确冲突时，才允许按照需求文档进行**最小范围修改**。

        ### 2. 不同层面的真源

        * **业务语义、权限、路由、状态流转、跨页数据后果、Action、Branch、Overlay、事务：以需求文档为准。**
        * **页面视觉和已有组件实现：以原 HTML 为准。**
        * **正式跨页面业务数据：最终以 GlobalStore 为唯一真源。**

        ## 三、严格按固定需求文档 Schema 整合

        需求文档格式固定。

        必须直接解析并执行需求文档中已有的：

        * `screen_manifest`
        * `web_shell_component_contracts`
        * `screen_component_contracts`
        * `global_behavior_templates`
        * `overlay_contract`
        * `branch_contracts`
        * `action_registry`
        * `workflow_states`
        * `page_lifecycle_contracts`
        * `shared_state_and_consequence_rules`
        * `navigation_and_return_rules`
        * `acceptance_criteria`

        不得自行建立与需求文档平行的另一套页面、Action、Branch、Overlay 或状态规则。

        如果 `page_integration_contract` 声明为最高权威，则其明确契约优先。

        ## 四、页面与组件绑定

        优先使用需求文档中的：

        * `html_file`
        * `screen_id`

        建立 HTML 与页面映射。

        存在 `match_mode / match / region / occurrence / element_kind` 时，按需求文档规则定位现有组件。

        匹配成功后可向合并副本注入稳定标识，例如：

        * `data-screen-id`
        * `data-component-id`
        * `data-action-id`
        * `data-overlay-id`

        禁止为了绑定契约而重建原组件。

        后续 Router、Action 和 Playwright 测试使用稳定 ID，不再依赖文本猜测。

        ## 五、最小侵入整合

        原则上只改以下系统边界：

        ### 正式数据

        原页面 Store / mock 正式数据

        →

        统一 `GlobalStore`

        ### 正式写操作

        原页面直接修改业务 Store

        →

        统一 `Action Dispatcher`

        ### 页面导航

        原页面独立导航

        →

        统一 `Router`

        ### 跨页实体

        多个页面分别保存同一实体

        →

        统一实体 ID + GlobalStore 中唯一数据

        ### 跨页刷新

        当前页面局部刷新

        →

        GlobalStore 更新后所有相关页面一致刷新

        ### Overlay 正式提交

        原 Overlay 直接写页面 Store

        →

        需求文档定义的 Action → GlobalStore

        除上述整合边界外，不得无必要修改原组件。

        ## 六、旧 Store 调用的迁移

        如果原组件已经调用：

        `sampleStore.xxx()`

        `applicationStore.xxx()`

        或其他页面 Store API，

        将这些调用改接 GlobalStore 的对应分区或 Action Dispatcher。
        允许无状态的函数转发以减少组件改动，但不得保留 PageStore/pageStore 对象、第二份实体数据或第二个 Store 实例。
        保留原组件 DOM 与局部交互，不得为了迁移状态而重写整个组件。

        ## 七、GlobalStore

        最终只能存在一个正式业务 GlobalStore。

        所有正式实体必须：

        * 使用稳定唯一 ID
        * 在 GlobalStore 中只存在一份
        * 跨页面通过 ID 引用
        * 同一实体在所有页面的数据保持一致

        合并后删除各 HTML 原有 Store 的实例和独立数据；无状态兼容函数只能转发到唯一 GlobalStore。

        页面局部状态仅允许保存：

        * UI 状态
        * 未提交 draft
        * 临时筛选
        * Overlay 临时输入
        * 地图临时交互状态

        统计、数量、KPI、状态汇总等 Derived State 必须从统一正式实体计算，不得多页分别维护。

        ## 八、Router

        最终只能存在一个 Router。

        Router 必须依据 `screen_manifest` 管理：

        * screen_id
        * route
        * route_params
        * role guard
        * history
        * return snapshot
        * Back / Forward
        * parent / fallback
        * 页面上下文

        禁止：

        * 第二套路由
        * 直接操作其他页面 DOM 实现导航
        * 页面独立维护 history
        * 跳转不存在的 screen_id

        ## 九、Action 与事务

        正式业务数据修改统一通过需求文档定义的 Action。

        执行顺序必须满足：

        事件
        → 原组件 handler
        → Adapter / Dispatcher
        → preconditions
        → permission
        → validation
        → version / idempotency 检查
        → transaction
        → GlobalStore 更新
        → affected screens 同步
        → success / failure consequence

        涉及多个实体的 Action 必须原子执行。

        失败时不得留下部分正式数据修改。

        Toast 不能代替契约要求的数据后果。

        ## 十、Overlay

        严格使用需求文档中的 `overlay_contract` 和 `overlay_registry`。

        如果原 HTML 已经存在符合要求的居中 Dialog / Popover：

        **必须复用原实现，不得重新创建。**

        原有右侧 Drawer 不符合本次布局要求，迁移其字段、校验、确认和取消行为到居中 Dialog 或已有详情页面。

        只允许适配：

        * 正式数据来源
        * confirm Action
        * GlobalStore
        * Router
        * affected screens

        必须保证需求文档要求的：

        * 打开条件
        * draft
        * 字段校验
        * confirm / cancel
        * Loading
        * 防重复提交
        * close policy
        * focus trap
        * focus restore
        * success / failure

        均真实生效。

        ## 十一、Branch、状态和权限

        * `RESOLVE_BRANCH` 必须通过需求文档的 `branch_contracts`。
        * 正式实体状态只能按照 `workflow_states` 流转。
        * 页面权限按照 screen 契约。
        * 组件权限按照 `preconditions / disabled_rule`。
        * 无权限 Action 不得仅靠视觉隐藏，业务执行层也必须阻止。

        ## 十二、交互完整性

        所有具有交互外观的元素必须属于以下一种：

        1. 正式业务 Action
        2. 明确的局部 UI 状态修改
        3. Router 导航
        4. Overlay 行为
        5. Branch 行为
        6. 明确 Disabled
        7. 纯展示且无可点击语义

        禁止：

        * 空按钮或空链接
        * 只 `console.log`
        * 只 Toast 而没有规定的数据后果
        * 直接修改其他页面 DOM
        * 绕过 Dispatcher 修改正式数据
        * 提交后相关页面不刷新
        * 跳转不存在的页面
        * 看似可点击但没有行为

        ## 十三、禁止功能降级

        禁止通过以下方式完成整合：

        * 删除页面
        * 删除组件
        * 隐藏需求要求的功能
        * 删除原有校验
        * 删除 Loading
        * 删除错误处理
        * 删除 Dialog 或右侧抽屉原有的业务能力
        * 删除分页、筛选或地图交互
        * 将原交互改为静态展示

        整合目标是保留现有页面能力并统一系统运行时。

        ## 十四、实现前检查

        修改前先建立并校验：

        * ScreenRegistry
        * RouteRegistry
        * ComponentRegistry
        * ActionRegistry
        * OverlayRegistry
        * BranchRegistry
        * EntityRegistry
        * WorkflowStateRegistry

        至少检查：

        * screen_id 唯一
        * route 唯一
        * component_id 唯一
        * action_id 唯一
        * overlay_id 唯一
        * target_screen_id 存在
        * dialog_id 存在
        * branch 输出有效
        * route_params 可解析
        * Action 引用实体有效
        * affected_screens 存在

        发现冲突不得静默忽略。

        ## 十五、Playwright 行为回归

        必须使用 Playwright。

        ### 合并前

        对原独立 HTML 中需求文档绑定的主要组件建立行为基线，记录：

        * click / input / change / submit
        * 字段联动
        * Validation
        * Loading
        * Disabled
        * Error
        * Dialog / Drawer / Popover
        * Tab / 筛选 / 排序 / 分页
        * 地图操作
        * 返回和焦点行为

        ### 合并后

        在 `merge.html` 对相同组件执行相同操作。

        允许变化：

        * 导航改为统一 Router
        * 正式数据改为 GlobalStore
        * 正式写入改为 Action Dispatcher
        * 跨页面数据同步
        * 权限和状态按照需求文档统一

        除此之外，原组件用户可观察行为必须保持等价。

        非必要变化视为回归错误。

        ## 十六、最终 Playwright 验收

        至少验证：

        * 所有 screen 和 route 可正确进入
        * route_params 能定位正确实体
        * 权限和 disabled_rule 生效
        * Back / Forward 和返回快照正确
        * 所有页面读取同一正式数据
        * 同一实体跨页面一致
        * Action 正确修改数据
        * affected screens 同步刷新
        * Derived State 同步
        * Branch 目标确定
        * Overlay 生命周期正确
        * draft 取消不污染正式数据
        * duplicate submit 被阻止
        * transaction failure 完整回滚
        * 不存在空交互
        * 不存在重复事件绑定
        * 不存在 console.error
        * 不存在 uncaught exception
        * 非当前页面不可点击或聚焦

        发现问题后必须：

        定位 → 最小修复 → 重测 → 完整回归。

        ## 十七、最终目标

        最终 `merge.html` 必须形成：

        * 一个 SPA
        * 一个 Router
        * 一个 GlobalStore
        * 一个 Action Dispatcher
        * 一套正式实体数据
        * 一套统一权限
        * 一套统一状态流转
        * 一套统一 Overlay / Branch / Action 运行机制	
		* 登录页面为默认页面

        同时最大程度保留所有独立 HTML 原有组件行为。
        
        最终结果必须是：

        **多个功能已经完整的独立页面，被最小侵入地整合成一个全局数据一致、页面跳转正确、状态同步正确、组件功能不回归的完整系统。**
        
        ## 十八、页面之间组件的一致性
        系统包含多个业务页面。对于在多个页面中承担相同功能的公共组件，必须检查其视觉和交互是否保持一致。
        登录页与业务页的按钮、输入框、卡片不属于同一视觉比较组

        重点检查：

        * 返回按钮
        * 顶部标题栏
        * 导航栏
        * 主按钮 / 次按钮
        * 输入框 / 搜索框 / Select
        * Tab
        * Card
        * Dialog / Drawer
        * Toast
        * Badge / Tag
        * 分页
        * 相同业务含义的 Icon Button
        检查原则

        * 先遍历全部页面，识别重复出现的公共组件，再进行跨页面比较。

        对于相同功能的公共组件，检查：

        * 组件形式
        * 图标
        * 图标尺寸和粗细
        * 高度 / 宽度
        * 圆角
        * 背景
        * 边框
        * 字体
        * 字号
        * 字重
        * 颜色
        * padding / gap
        * hover / active / disabled 状态
        * 交互行为

        不得只比较 class 名称，必须结合：

        * DOM
        * computedStyle
        * getBoundingClientRect()

        进行判断。

        同一种组件允许因为内容长度、页面宽度等产生合理尺寸变化，但不得出现没有业务原因的视觉变体。

        例如以下情况应判定为 FAIL：

        * 页面 A 返回使用单独左箭头，页面 B 使用“返回”胶囊按钮；
        * 相同层级页面的 Header 高度明显不同；
        * 同类 Primary Button 在不同页面使用不同颜色或圆角；
        * 相同 Search 输入框在不同页面样式不同；
        * 同一级  Navigation 的结构、图标、顺序或选中方式不同；
        * 相同 Tab 一页使用下划线，一页使用胶囊；
        * 相同 Dialog 的标题栏、圆角和按钮布局明显不同；
        * 相同业务动作使用不同图标。

        不要把合理的业务 Variant 误判为问题。

        例如：

        * Primary Button 与 Danger Button；
        * 普通 Card 与明确的 Warning Card；
        * 普通状态 Badge 与危险状态 Badge；

        这些具有明确业务语义的差异可以保留。

        手机 App 特别检查

        * 一级主页面通常不显示返回按钮；
        * 二级及更深页面的返回组件必须保持统一；
        * 如果多数正常页面使用单独左箭头返回，则其他同级页面不得无理由使用“返回”胶囊、文字按钮或其他形式；
        * Bottom Navigation 只应出现在需求定义需要显示的页面；
        * Bottom Navigation 在不同一级页面中必须保持：
        * 项目数量一致；
        * 项目顺序一致；
        * 图标体系一致；
        * 高度一致；
        * 背景一致；
        * active / inactive 样式一致；
        * 只改变当前选中项。
		
        【登录页要求】
        * 登录页属于独立视觉页面，不参与业务页外壳、主内容边界、
        * 公共组件和共享显示规则的统一；保留其原有布局、装饰区、字体、输入框、按钮及响应式效果。
        * 业务公共 CSS 必须限定在业务页面作用域内。
        * 使用 Shadow DOM 时，不得向登录页注入业务公共 CSS。
        * 不得为了 SPA 适配改变登录页原有的 Grid/Flex 布局方式；必要的根选择器和容器高度调整必须保持原页面视觉等价。
        * 在相同视口和交互状态下，对比原登录页与合并登录页：
        * 截图、主要区域的位置与尺寸，以及关键控件的 computedStyle。
        * 装饰区域消失、卡片偏移或控件样式被覆盖，均判定为回归
		
		【本次整合的最高优先级修复要求】
        * 必须读取统一共享数据 {shared_context_path}，以其实体 ID、字段、统计口径和显示规则为依据；不能让各独立页分别保留正式数据副本。
        * merge.html 只维护一个 GlobalStore 实例和一份正式实体；禁止 PageStore、pageStore、第二套业务 Store 及通过 Facade/Adapter 暗中保存独立数据。
        * 页面草稿、筛选、Tab、Dialog 和临时 UI 状态统一存入 GlobalStore 的页面分区；正式写入通过 Action Dispatcher。
        * 只能存在一个 Router。独立页的 navigate 接口统一接入 SPA Router，移除组件内文件跳转、独立 history、重复导航和重复事件绑定。
        * 除了登录页面外，各业务页面的主内容容器填满导航、顶栏之外的可用区域，外层容器适配可用区域，内部组件同步调整，避免固定尺寸造成大块空白。按需调整宽高限制，保留合理比例和滚动机制；禁止批量清除高度及 Grid 约束，不得为填满页面拉伸图表，也不得让表格内容撑高相邻图表。
        * 移除主内容区上方的页面描述及左上角说明性副标题。禁止右侧抽屉，原功能改为居中弹窗或已有详情页面，保留校验、取消和业务后果。
        * 除了登录页外，各业务页面统一同层级标题、正文、表头、标签和辅助文字的字号、字重、行高，以及表单内边距和字段间距；不得出现贴边、遮挡、裁切或布局造成的大块无效空白。
        * 二维码必须可解码且编码内容对应正确实体，所有资源须内嵌以供离线使用；禁止把参考图中的装饰图案当作二维码。
        * 编号不得按记录序号连续递增；时间不得按固定分钟、小时、天数递增，仍须满足业务先后关系。
        * 卡片、表格、详情、筛选结果、分页总数和跨页统计均基于同一实体集合及统计口径，页数从筛选后总数和页大小计算。
        * 业务页面较多或一级菜单超出可用高度时，按业务模块采用二级导航；详情和编辑页不自动成为一级菜单。
        * 用户名和密码均为admin，且默认已填充
        * 保持原 HTML 的主要区域结构、位置关系、卡片行列数、组件顺序和布局比例。如原本五张卡片一行，合并后仍是一行，不重新排列页面。
        * 主内容区填满导航、顶栏之外的可用区域，内部布局按原结构自适应，避免固定尺寸造成大片无效空白。
        * 允许统一组件样式、统一同层级文字的字体、字号、字重和行高，以及同类按钮、输入框、卡片的尺寸规则、间距、边框和圆角。保留危险态、禁用态等必要差异。统一样式导致尺寸变化时，调整必要的容器空间和内部对齐，保证文字、控件完整显示；不得因此改变主要区域结构、卡片行列或组件顺序。
        * 图表按实际容器重新计算尺寸，图形、图例和标签完整可见；表单和浮层无遮挡。
        * 用真实浏览器验证：原布局结构是否保持、公共样式是否一致、内容区是否充分利用，以及是否存在文字溢出、图表越界、组件遮挡或新增异常空白。
        * 必须使用 business-specific-coding skill ，否则报错终止执行
        
       【显示问题专项检查】
        * 实际遍历所有页面默认态，以及主要 Tab、菜单、时间选择器、表单弹窗和错误提示态。等待字体、图片和图表稳定后检查，不能只验证组件存在、isVisible 或点击成功。
        * 遮挡：在组件内部中心和边缘取多个点，用 elementsFromPoint 检查命中是否属于该组件或其子节点；结合实际截图判断视觉遮挡，不能仅检查 z-index。
        * 裁切：检查元素与视口、各级裁剪祖先的边界关系，读取祖先 overflow、clip-path 等属性。弹窗内文字和主要按钮必须完整可见或可通过预期滚动到达。
        * 文字溢出：比较 scrollWidth/clientWidth、scrollHeight/clientHeight，并用 Range.getClientRects 检查实际文字行是否被容器或祖先裁切，不能只检查文本容器尺寸。
        * 图表越界：检查实际图形、坐标轴、图例和标签，不只检查外层容器。SVG 检查变换后的图形边界；canvas 图表结合实际渲染截图核对。
        * 排除误报：合法滚动、允许的省略、隐藏状态及浮层跨父容器定位不直接判错；必须依据业务规则判断内容是否可读、操作是否可达。
        * 禁止页面最右侧的整体纵向滚动条，表格、列表、工作区、弹窗正文等内部容器允许使用滚动条
        """).strip()
    
    prompt = f"""
        需求文档：
        {requirement_file}

        HTML 目录：
        {html_dir}

        本次唯一允许合并的独立 HTML 清单：
        {source_file_list}

        共享数据与显示规则：
        {shared_context_path}

        保存为：
        {os.path.join(html_dir, 'merge.html')}
        
        1、输入限于 {requirement_file}、{shared_context_path} 和上面的独立 HTML 清单；不要把旧 merge.html、备份 HTML 或测试页面当作待合并页面。允许在 {html_dir} 写入本次验收证据。
        2、{('* 所有页面使用统一的手机系统状态栏（时间/信号/WiFi/电量，不要电量比例）\n '
              '* 使用统一的底部导航栏，登录页面不显示底部导航栏,只在一级主页面显示底部导航栏，所有通过这些主页面进一步进入的详情、编辑、操作和流程页全部隐藏底部导航栏'
              '* 所有页面（除了登录页）的页面标题在页面中的高度必须相同、水平居中、文字样式大小相同'
              '* 手机系统状态栏的高度为60px、状态栏图标（包括 时间/信号/WiFi/电量）为35px，其中时间的字号大小为30px、font-weight: 400'
              '* 底部导航栏的高度为114px、图标 + 文字的整体视觉高度为65px'
              '* 手机系统状态栏上方和底部导航栏下方禁止出现空白区域'
              '* 底部导航栏风格和待合并的html风格保持一致')
            if cate=='手机app' else '* 除了登录页外，各个页面使用统一的导航栏，导航栏风格和待合并的html风格保持一致'}
        """ 
    prompt = PROMPT +'\n' + prompt
    
    if tool == 'opencode':
        cmd = [OPENCODE_CMD, "run", "--auto","--dir",CWD,"-m", DEEPSEEK_V4_PRO, '--variant', 'max',"--dangerously-skip-permissions", prompt]
    else:
        cmd = [
            CLAUDE_BINARY,
            'exec',
            '-m', MERGE_THML_MODEL,
            '-c', f'model_reasoning_effort={MERGE_THML_MODEL_EFFECT}',
            '-C', work_dir,
            '-c', 'project_root_markers=[]',
            '--dangerously-bypass-approvals-and-sandbox',
            prompt
        ]
    process = subprocess.Popen(
        cmd,
        cwd=work_dir,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    for line in process.stdout:
        print(line)
    process.wait()



    # if process.wait() != 0:
        # raise RuntimeError('合并 HTML 命令失败')
    # validate_stage_outputs('merge', html_dir)
    
    
def check_and_repaire_html(requirement_file, html_path, cate='web',tool='opencode'):
    import contextlib
    import datetime
    import json
    import math
    import time
    import uuid

    # 所有计时、日志辅助函数均保留在当前函数内部。
    _run_started = time.perf_counter()
    _run_id = datetime.datetime.now().astimezone().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    _log_dir = Path(html_path).expanduser().resolve().parent / 'html_check_logs' / _run_id
    _log_dir.mkdir(parents=True, exist_ok=False)
    _summary_path = _log_dir / 'timing_summary.json'
    _events_path = _log_dir / 'events.jsonl'
    _summary = dict(run_id=_run_id, html_path=str(Path(html_path).resolve()),
                    tool=tool, status='RUNNING', phases=[],
                    notes='阶段时间为父进程实测墙钟时间；TIMING 细项来自子进程，可能重叠，不能直接累加。输出时间戳为父进程收到该行的时间。')

    def _now():
        return datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')

    def _save_summary():
        _summary['updated_at'] = _now()
        _summary['elapsed_seconds'] = round(time.perf_counter() - _run_started, 3)
        _temporary = _summary_path.with_suffix('.tmp')
        _temporary.write_text(json.dumps(_summary, ensure_ascii=False, indent=2), encoding='utf-8')
        _temporary.replace(_summary_path)

    def _event(kind, **fields):
        data = dict(timestamp=_now(), run_elapsed_seconds=round(time.perf_counter()-_run_started, 3), event=kind, **fields)
        with _events_path.open('a', encoding='utf-8') as output:
            output.write(json.dumps(data, ensure_ascii=False) + '\n')

    @contextlib.contextmanager
    def _timed_phase(phase_id, label):
        started = time.perf_counter()
        record = dict(id=phase_id, label=label, status='RUNNING', started_at=_now(),
                      log_path=str(_log_dir / (phase_id + '.log')),
                      output_lines=0, reported_timings=[], longest_output_gap_seconds=0.0)
        _summary['phases'].append(record)
        _event('phase_start', phase=phase_id, label=label)
        _save_summary()
        print(f'[计时] 开始：{label}；日志目录：{_log_dir}', flush=True)
        try:
            yield record
        except BaseException as exc:
            record['status'] = 'INTERRUPTED' if isinstance(exc, KeyboardInterrupt) else 'ERROR'
            record['error'] = f'{type(exc).__name__}: {exc}'
            raise
        else:
            record['status'] = 'COMPLETED'
        finally:
            ended = time.perf_counter()
            record['elapsed_seconds'] = round(ended - started, 3)
            record['ended_at'] = _now()
            record.pop('_started_monotonic', None)
            last_output = record.pop('_last_output_monotonic', None)
            if last_output is not None:
                record['longest_output_gap_seconds'] = round(max(record['longest_output_gap_seconds'], ended-last_output), 3)
            _event('phase_end', phase=phase_id, status=record['status'], elapsed_seconds=record['elapsed_seconds'])
            _save_summary()
            print(f'[计时] 结束：{label}；{record["elapsed_seconds"]:.2f} 秒；{record["status"]}', flush=True)

    def _record_line(record, output, line):
        received = time.perf_counter()
        stage_elapsed = received - record['_started_monotonic']
        gap = received - record['_last_output_monotonic']
        record['_last_output_monotonic'] = received
        record['output_lines'] += 1
        record['longest_output_gap_seconds'] = max(record['longest_output_gap_seconds'], round(gap, 3))
        prefix = f'[{_now()}][{record["id"]} +{stage_elapsed:.3f}s][gap={gap:.3f}s] '
        output.write(prefix + line)
        if not line.endswith('\n'):
            output.write('\n')
        output.flush()
        print(line, end='', flush=True)
        # CLI 可能在标记前加前缀，因此查找标记位置；无法解析的原文仍完整保留。
        marker = '[TIMING] '
        position = line.find(marker)
        if position >= 0:
            try:
                data, _ = json.JSONDecoder().raw_decode(line[position+len(marker):].lstrip())
                seconds = data.get('elapsed_seconds') if isinstance(data, dict) else None
                if (isinstance(data, dict) and isinstance(data.get('step'), str)
                        and type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0):
                    timing = dict(step=data['step'], elapsed_seconds=seconds,
                                  source='child_reported', received_at=_now(),
                                  stage_elapsed_seconds=round(stage_elapsed, 3),
                                  measurement=data.get('measurement', 'unspecified'))
                    record['reported_timings'].append(timing)
                    _event('reported_timing', phase=record['id'], **timing)
                    _save_summary()
            except (ValueError, TypeError):
                pass

    _summary['started_at'] = _now()
    _save_summary()
    _event('run_start')
    try:
        shutil.copy(html_path, html_path.replace('.html','_bk.html'))
        save_dir = Path(html_path).parent.resolve()
        # validate_stage_outputs('shared_context', save_dir)
        shared_context_path = save_dir / 'shared_context.json'

        scope_rules = textwrap.dedent("""
            # 最高优先级：以现有 HTML 组件确定检查和修复范围

            本任务是修复现有 HTML，不是按需求文档补建整个系统。
            HTML 决定“检查哪些对象”，交互需求文档用于判断这些对象“应如何工作”。
            以下范围约束优先于后文的需求优先、全量验收、完整业务后果、全量回归等表述。

            1. 在修改前结合 HTML 源码、动态渲染代码和真实浏览器建立现有范围清单：
               已有页面、模块、组件、入口、数据展示及其关联功能。
               暂时隐藏、需要切换 Tab 或触发弹窗才显示、因故障无法进入的已有内容也在范围内。
               范围清单须写入 html_acceptance_report.md，作为修复和回归的固定基线。
            2. 凡 HTML 中已有的组件，其功能、数据和 UI 都必须检查并修复。
               即使按钮只有外观、没有事件处理、使用空函数或只有占位反馈，也属于待修复问题，
               必须补写该组件应有的业务行为，不能标为范围外或以“尚未实现”为由跳过。
               例如：已有搜索框必须能搜索；已有保存按钮必须校验并保存；已有 Tab 必须能切换。
            3. 需求文档中定义、但 HTML 中完全没有的独立模块、页面、组件或功能入口，
               标为 OUT_OF_SCOPE（现有 HTML 未包含，本次不补建）。
               不将其记为 FAIL、缺失缺陷、NOT_TESTED 或待修复事项，不纳入覆盖率分母。
               例如：需求要求导出，但 HTML 没有导出入口或对应实现，不新增导出功能。
            4. 为使已有组件正常工作，允许补写其直接必要的事件处理、校验、状态和数据更新、
               导航连接、弹窗、结果展示和反馈。这属于修复已有组件，不属于补齐独立需求。
               例如：已有“编辑”按钮但没有编辑弹窗，应补齐该按钮所需的编辑及保存交互；
               不得因此继续新增需求文档中其他无关的页面、字段、菜单或完整业务模块。
               必要依赖的新增必须说明其服务的原有组件及最小实现范围，不得无限追补需求依赖链。
            5. 已有组件按需求中与其直接相关的业务规则检查；文档没有对应定义时，
               根据组件文案、上下文和已有同类交互判断，不臆造新业务。
               不得把更改组件文案、删除/隐藏组件、永久禁用、空处理或虚假成功提示当成修复。
            6. 后文所有“全部”“逐个”“必须”“与 XML 一致”均限于上述范围；
               页面、分支、弹窗、事务、角色、数据实体和业务示例只检查实际适用项。
               对 merge.html 必须验证并修复唯一 GlobalStore 和唯一 Router；禁止 PageStore/pageStore、第二份正式实体数据或独立 history。
               其他没有现成入口的独立后台服务不要求补建，重点验证实际功能、数据一致性和 UI 是否正确。
            7. 每项缺陷必须关联修改前已存在的页面/组件，并给出 DOM、源码或浏览器证据。
               OUT_OF_SCOPE 单独列出，不能影响现有范围的通过结论。
               范围内因环境或必要依赖受限而无法验证的项目须标为 BLOCKED / NOT_TESTED，
               不得伪报 PASS，也不得因为修复困难而移出范围。
            8. 修复阶段必须先按以上规则复核验收报告；即使报告把完全不存在的独立需求列为缺陷，
               也应改列 OUT_OF_SCOPE 并说明，不执行补建。回归沿用原有范围，并覆盖修复新增的必要依赖。
            9. 本次问题清单中的布局、编号、时间、统计、二维码、表单按钮截图前置行为、GlobalStore 和 Router 要求优先于旧 HTML 视觉与旧 Store 兼容规则
               * 登录页仅豁免业务页的视觉统一要求，包括页面外壳、主内容边界、文字和公共组件样式；仍须接入唯一 GlobalStore、Router，并接受认证、权限和交互功能检查。同一视口下，使用业务外壳的页面主内容边界一致并填满可用区域：登录页保留原独立 HTML 的布局与样式。
               * 禁止主内容区上方页面描述、左上角说明性副标题和右侧抽屉；原抽屉业务能力必须移至居中弹窗或已有详情页面。
               * 同一视口下，使用业务外壳的页面主内容边界一致并填满可用区域；这些业务页面中同层级文字的字号、字重、行高一致。登录页除外
               * 表单文字与组件远离边界，无遮挡、裁切及布局造成的大块无效空白。
               * 编号不能机械连续递增；时间不能固定分钟、小时或天数递增，正常业务排序仍需正确。
               * 同一实体跨页字段一致；同口径统计由真实实体计算；分页总数与筛选后完整集合一致。
               * 二维码从实际渲染结果解码并核对实体载荷，不能仅检查外观。
               * 验证表单内部按钮的校验失败、合法提交、取消及适用的重置结果，为最终截图提供可复现状态。
            10. 禁止使用任何 skill。检查、修复和回归必须使用浏览器证据；无法验证不得标为 PASS。
        """).strip()

        PROMPT = textwrap.dedent(f"""
            # 第一阶段：范围内浏览器检查与缺陷定位

            当前界面类型：{cate}。共享数据路径：{shared_context_path}。
            本阶段只检查，不修改任何业务文件；允许在指定产物目录创建测试脚本、证据和报告。
            目标是用一次有组织的浏览器检查发现现有组件的真实问题，输出可直接用于第二阶段的修复清单。
            以下范围规则保持有效；范围内项目都要登记和检查，但基础检查与深度场景覆盖必须分开统计。
            受本次执行策略限制未执行的细分场景如实标 NOT_TESTED，不将基础操作成功写成该组件所有合同通过。

            {scope_rules}

            # 一、输入与固定清单
            1. 读取 HTML 和共享数据，结合真实浏览器建立已有页面、组件、入口、隐藏区域和必要依赖清单。
               需求文档只完整读取一次并建立索引；提取与现有范围直接对应的规则，后续按定位读取片段。
               不反复全文读取，不重新设计系统，不逐条展开无关业务示例。
            2. 为页面、组件和测试场景建立稳定 ID；记录需求引用、前置条件、预期结果、证据路径及状态。
               已有组件缺少应有行为必须记为缺陷，不能当范围外；实际不适用项须说明依据，不能用于隐藏未实现行为。
            3. 记录 HTML/共享数据/需求的校验值、视口、角色和测试初始状态，便于第二阶段判断证据是否仍有效。

            # 阶段交接：为第二阶段直接提供可执行的定位与回归信息
            生成 {save_dir / 'html_repair_handoff.json'}，而且只生成一份。它是本阶段报告的结构化索引，不额外进行一轮测试。
            文件记录本次 HTML、需求和 shared_context 的 SHA-256、范围清单路径及测试环境；每条确认缺陷须含稳定 Issue ID、严重度、
            已有组件/页面、源文件与可定位的唯一文本/函数名或源码区间、需求规则、复现前置条件、浏览器断言、证据文件路径、
            候选共因组、影响页面/实体，以及可直接执行的复现命令和回归命令。
            原因尚未确认时标记“待定位”，不要臆造行号或修复方式。把误报、NOT_TESTED 与已确认缺陷分开，明确哪些脚本已可靠通过。
            脚本中固定输入、角色、初始数据与成功/失败断言，运行时输出测试 ID、退出码和耗时；一份脚本可以覆盖多个 Issue。
            第二阶段应可通过此文件快速找问题和复用脚本，不需要再次枚举所有源码和 JSON 证据。

            # 大文件与命令执行规则
            merge.html 如有单行内嵌整页脚本，建立一次页面 ID -> 片段/关键函数定位索引，之后按片段读取。
            搜索输出限制在匹配位置与邻近必要上下文；不得把整个单行 HTML、内嵌整页 JS、完整 DOM、巨型 JSON 或截图编码输出到控制台。
            宽泛搜索无结果时先检查精确关键字、编码或文件结构，不反复运行等价命令。
            真实脚本测试仍在真实浏览器中执行；输出摘要不能代替断言与原始失败证据，完整细节可留在证据文件。

            # 二、一次执行，避免全组件重复复测
            1. 使用一个 HTTP 服务和一个浏览器进程，编写一套可复用的 Playwright 或等价浏览器脚本。
               不为每个报告章节分别生成测试工具；不要把开发测试框架本身当成任务。
            2. 按页面和完整业务流程组织操作。同一流程覆盖多个组件/Action 时，共享真实证据，不重复点击。
               同一业务流程内保持会话与实体连续，特别是写入后的跨页核对；不同破坏性流程使用隔离初始状态。
               只读检查按角色复用上下文，不为每个按钮单独建上下文、登录、导航。
            3. 首轮遍历全部已有页面；故障页面记录原因，其余页面继续。每个组件执行一次适用的基础行为及结果断言。
               页面/组件计数必须去重，区分已执行、通过、失败、阻塞和未测；点击完成本身不等于业务通过。
            4. 首轮结束后只复测失败判定存疑、测试脚本错误或受前序状态污染的项目；禁止无理由对全部组件再跑一轮。
               同一脚本某断言失败时先检查导航/定位器和状态污染；脚本修复只重跑被改动的用例，保留原始异常和最终判定。
               每个相同阻塞最多进行一次有针对性的排查或重试；条件未改善不重复等待。
               修正测试脚本时保留原始日志和修改原因，不降低断言；只重跑受脚本修正影响的测试。
            5. 默认使用一个目标视口：优先采用输入指定尺寸，否则 web 用 1440×900，移动界面按需求尺寸。
               第二视口只用于明确的响应式验收要求或疑似断点问题；不自动把角色×页面×视口×状态做笛卡尔积。
               输入要求但本次未执行的视口覆盖应标 NOT_TESTED，不能声称已全面验证响应式。

            # 三、基础检查覆盖全部已有页面与组件
            - 页面进入、必需路由参数、主导航、页面内入口、Tab、返回和前进后退；同一实现的深入状态恢复按代表路径验证。
            - 搜索/筛选/排序/分页的可见结果与集合总数；编辑/保存/取消/重置、上传等已有功能的实际业务后果。
            - 每个已有表单至少验证合法提交、适用的校验失败、取消和重置；相同校验规则的深度边界场景选代表字段，列出未覆盖项。
            - 每个可触发弹窗检查打开、内容、主操作、关闭及状态后果；已有右侧抽屉记录为迁移缺陷。
            - 每类关键写操作都需在同一会话中重新进入其直接影响页面，核对相同实体、统计和分页；不能只看 toast 或内存变量。
            - 真实浏览器批量采集主内容边界、文字层级、表单内边距、溢出、遮挡及公共组件样式；记录异常，正常明细放 JSON。
            - 根据运行时实体核对编号、时间排序、同一实体跨页字段和同口径统计；不枚举无关实体类型。
            - 检查已有二维码时对实际渲染码解码并核对载荷；无二维码入口则不补建。
            - 检查唯一 GlobalStore/Router、正式实体来源及 history。静态检查用于定位，功能通过必须有浏览器证据。
            - 全程收集 console.error、pageerror、资源失败；异常按根因去重。

            # 三补充、跨页面视觉协调性（纳入上述首轮遍历，不另跑全组件测试）
            1. 遍历全部已有页面，把组件按语义、导航层级、业务 variant、交互状态及视口/主题分组。
               不能仅按 h1/h2 标签名、class 名或外观相似分组；相同语义层级即使标签不同也要比较。
               每个页面上的同类组件实例都纳入默认状态对照，不能只比较报告中举例的两个页面。
            2. 批量采集真实 computedStyle 与 getBoundingClientRect，显式对照以下属性：
               - 同层级标题、正文、辅助文字：font-family、font-size、font-weight、line-height、letter-spacing、color。
               - 同类主/次按钮：高度、宽度规则、padding、gap、圆角、背景色、文字色、边框、图标尺寸及图文间距。
               - 输入框、搜索框、Select：高度、字号、行高、内边距、边框、圆角、背景色与 placeholder 样式。
               - 卡片、弹窗：内边距、区域间距、圆角、阴影、标题样式、按钮排列及对齐方式。
               - Header、导航栏、Tab、返回按钮：高度、位置/对齐、图标尺寸与粗细、间距、颜色和选中样式。
               - 表格、分页：表头字号/字重/颜色/背景、行高、单元格内边距、操作按钮及分页控件样式。
               - 页面整体：主内容边界、同层级标题起始位置、水平对齐、内容留白及组件密度是否无理由突变。
            3. 比较必须在相同语义、层级、业务 variant、状态、视口和主题条件下进行。
               主按钮与危险按钮、普通卡片与警告卡片等合理差异保留；文案不同导致按钮宽度变化、多行内容导致行高变化不机械判错。
               响应式布局、父容器可用宽度、浏览器原生控件和亚像素舍入差异要结合上下文判断，不能要求所有宽高数值完全相等。
               CSS 颜色表示须先归一化；字体回退栈文字不同但实际显示一致不能直接认定视觉缺陷。
            4. 对 hover、focus-visible、pressed/active、selected、disabled、error 等适用状态，按共享实现选择代表实例真实触发并采集。
               不同实现或独立样式覆盖分别验证；同一组件不能拿默认态与另一组件禁用态比较。
               未逐实例验证的状态必须注明代表测试范围，不能写成全部状态已通过。
            5. 需求或现有明确的设计规范优先；没有规范时，选系统中广泛使用、结构合理且符合整体风格的实现作为基准并说明依据。
               若同类实例各自一致但整体尺寸、对齐或颜色搭配明显不协调，按需截图判断，不仅凭数值一致就认定视觉协调。
               不因个人审美偏好新增设计要求；基准存在疑义时记录待确认，不擅自重设计整个系统。
            6. 每项差异给出组件分组、Page A/组件、Page B/组件、状态/视口、具体属性与实际值、基准和合理性判断。
               同一公共规则导致的多个差异合并为一个根因组，列全受影响页面；正常样式明细放 JSON，报告仅列异常和覆盖汇总。
               几何或样式差异需要视觉确认时才截图，不因增加本节而恢复逐组件截图或第二轮全页面采集。

            # 四、深度场景按风险执行，不无限构造条件
            1. 认证、权限、不可逆写操作、重复提交和事务一致性优先；认证存在时包含错误凭据，权限存在时包含越权直达和关键 Action。
            2. 不同组件共用同一段校验、弹窗或权限实现，且源码证据表明没有独立分支时，允许选择代表项深测。
               所有实例仍做基础检查。代表项通过只证明该用例通过，不自动填充未执行实例的独立状态为 PASS。
            3. 分支优先覆盖当前可构造的正常路径和关键失败路径；不为了遍历罕见状态大量制造实体、修改业务文件或补写后端。
               可建立不修改业务文件的隔离 fixture 作为前置条件，记录来源；触发及结果验证仍通过真实 UI，不直接改 Store 冒充业务成功。
            4. 网络故障、版本冲突、子事务失败、加载期间多次 Enter 等只在相关业务机制存在且能在现有测试条件中可靠构造时执行。
               应有机制缺失属于缺陷；机制存在但构造受阻记 BLOCKED；仅本轮未深测记 NOT_TESTED；确实不适用须说明依据。
            5. 焦点陷阱、焦点归还、事件泄漏等共用机制选择代表实例深测，发现异常再扩大到受影响实例，不先穷举所有组合。

            # 五、截图按需，浏览器证据不等于截图
            1. 不要求每页、每个组件、每次操作或每个成功状态截图；基础功能用真实浏览器操作与结构化断言证明。
            2. 仅在视觉异常需要确认、DOM 证据不足或关键问题需要复现图时截图，优先截相关区域。
               同一页面、视口与状态只保留一份证据图，可关联多个 Issue；不因报告章节不同重复截图。
            3. 正常流程不截图、不录制视频、不保存全程 trace；失败定位确有需要时才短程采集。
               不逐张查看无异常图片，不输出图片 base64。二维码解码所需的渲染图像可临时采集，不扩展为全页面截图。
            4. 表单后续截图状态只需记录操作顺序、输入和预期状态，不在本阶段生成最终交付截图集。
            5. 渲染外观无法通过当前证据判断的细节如实标未验证，不能仅凭尺寸断言所有视觉细节通过。

            # 六、报告与停止条件
            1. 完成一轮基础检查、风险优先深测及必要的局部纠错后结束，不为消灭所有 NOT_TESTED 不断追加测试。
            2. 生成 html_acceptance_report.md，包含：范围基线、运行环境、覆盖统计、页面摘要、按根因分组的问题、BLOCKED/NOT_TESTED/不适用项及结论。
               每项缺陷写 Issue ID、严重度、已有组件证据、需求引用、实际/预期、最短复现、证据、疑似根因、影响范围和建议回归用例。
               疑似根因不能当作已确认事实；复测纠正的误报要明确撤销，不保留互相矛盾的摘要。
            3. 修复报告应明确引用 html_repair_handoff.json。正常字段的坐标、样式、实体样本和逐步记录保存在结构化证据中，正文只放异常值与汇总，不重复倾倒大表。
               保存可直接复用的测试脚本、测试清单、运行命令、fixture 和证据索引，并在报告中给出路径。
            4. 页面基础覆盖、深度场景覆盖分别统计，分母沿用已有范围；不得把 EXECUTED、打开弹窗或源码推测写成完整 PASS。
               最终结论只能为 PASS、PASS_WITH_MINOR_ISSUES 或 FAIL；有范围内失败、阻塞或未测项时不得宣称完整 PASS。
            5. 在控制台输出各步骤计时：输入分析、脚本准备、首轮执行、局部复测、截图采集、报告生成和整个阶段总耗时。
               截图耗时记录为测试内子项，避免重复相加；说明模型阅读/分析等无法单独精确计量的部分。


            # 七、耗时日志输出协议
            在步骤真正开始时即时输出并刷新 [STEP_START]，真正完成时输出并刷新 [STEP_END]。
            禁止在最后集中补印旧步骤标记，也不要重复输出同一条已记录的 [TIMING]；尚未执行或因中断未结束的步骤不能伪称完成。
            如需归纳步骤，只在最终报告列摘要，不再使用 START/END 标记冒充实时计时。
            对可用脚本实际计时的步骤，额外单行输出 [TIMING] 后接 JSON 对象，字段为 step、elapsed_seconds、measurement。
            step 为具体步骤名，elapsed_seconds 为实际测得的非负秒数，measurement 固定为 measured。
            用脚本单调时钟测量脚本准备/执行、局部复测、截图与报告生成等能可靠计时的部分；无法实际测得的模型分析时间只输出步骤标记，不编造秒数。
            截图时间可能包含在测试总时间中，不能把所有细项直接累加成阶段总时间。
            计时行必须实际输出到控制台，不仅写在报告里，不要只在最终答案重复一个总数。
            
            # 八、显示问题专项检查
            实际遍历所有页面默认态，以及主要 Tab、菜单、时间选择器、表单弹窗和错误提示态。等待字体、图片和图表稳定后检查，不能只验证组件存在、isVisible 或点击成功。
            1. 遮挡：在组件内部中心和边缘取多个点，用 elementsFromPoint 检查命中是否属于该组件或其子节点；结合实际截图判断视觉遮挡，不能仅检查 z-index。
            2. 裁切：检查元素与视口、各级裁剪祖先的边界关系，读取祖先 overflow、clip-path 等属性。弹窗内文字和主要按钮必须完整可见或可通过预期滚动到达。
            3. 文字溢出：比较 scrollWidth/clientWidth、scrollHeight/clientHeight，并用 Range.getClientRects 检查实际文字行是否被容器或祖先裁切，不能只检查文本容器尺寸。
            4. 图表越界：检查实际图形、坐标轴、图例和标签，不只检查外层容器。SVG 检查变换后的图形边界；canvas 图表结合实际渲染截图核对。
            5. 排除误报：合法滚动、允许的省略、隐藏状态及浮层跨父容器定位不直接判错；必须依据业务规则判断内容是否可读、操作是否可达。
            6. 每项记录页面、状态、组件、实测边界、裁剪祖先、命中结果和证据。无法确认标记 NOT_TESTED，不得默认 PASS。发现问题后修复，并重放同一状态验证。
        """).strip()
    
        prompt = PROMPT+'\n'+f'交互需求文档路径:{requirement_file}\n共享数据路径:{shared_context_path}\nHTML路径:{html_path}\n报告及测试产物目录:{save_dir}\n业务输入仅限上述需求文档、共享数据和 HTML；允许在产物目录创建、读取本次验收报告、测试脚本和浏览器证据。禁止修改业务文件或访问无关文件。'

        if tool == 'opencode':
            cmd = [OPENCODE_CMD, "run", "--auto","--dir",CWD,"-m", DEEPSEEK_V4_PRO, '--variant', 'max',"--dangerously-skip-permissions", prompt]
        else:
            cmd = [
                CLAUDE_BINARY,
                'exec',
                '-m', REPAIRE_MODEL,
                '-c', f'model_reasoning_effort={REPAIRE_MODEL_EFFECT}',
                '-C', CWD,
                '-c', 'project_root_markers=[]',
                '--dangerously-bypass-approvals-and-sandbox',
                prompt
            ]
        with _timed_phase('stage_1', '第一阶段：检查与报告') as _stage:
            _stage_clock = time.perf_counter()
            process = subprocess.Popen(
                cmd,
                cwd=save_dir,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,

            )

            _stage['pid'] = process.pid
            _stage['_started_monotonic'] = _stage_clock
            _stage['_last_output_monotonic'] = _stage_clock
            _save_summary()
            with open(_stage['log_path'], 'a', encoding='utf-8') as _output_log:
                for line in process.stdout:
                    _record_line(_stage, _output_log, line)

            _stage['returncode'] = process.wait()
            if _stage['returncode'] != 0:
                raise RuntimeError('HTML 初次验收命令失败')
        with _timed_phase('stage_1_report_check', '第一阶段报告检查'):
            if not (save_dir / 'html_acceptance_report.md').is_file():
                raise RuntimeError('HTML 初次验收报告缺失')
    
    
    
        PROMPT = textwrap.dedent(f"""
            # 第二阶段：按已确认缺陷批量修复，并完成有边界的浏览器回归

            当前界面类型：{cate}。共享数据路径：{shared_context_path}。
            本阶段以第一阶段的既有范围和已确认问题清单为基础，修复真实缺陷。
            目标不是重建系统、重写测试框架或不断扩展测试范围。未完成项必须报告，不强行做到全项 PASS。

            {scope_rules}

            # 先使用第一阶段交接索引，减少重复定位
            首先读取 {save_dir / 'html_repair_handoff.json'} 与 html_acceptance_report.md，并核对三份输入的 SHA-256。
            索引存在且与当前文件匹配时，直接按 Issue 的源码定位、浏览器断言与命令工作，不重新枚举全部页面源码/证据。
            索引不存在、损坏或哈希不匹配时，说明原因后从报告和既有脚本建立最小必要替代索引，不无限搜索。
            先按风险对已确认 Issue 分组；仅对需确认根因的 Issue 运行其最短复现脚本，然后尽早批量修改对应代码。
            不要为每个 Issue 新建一套基线/盒模型/样式探针；只有证据不能区分根因时才补写一个有明确判定目标的探针。
            尤其避免在开始修改前完整运行所有组件与所有页面第二次；已有证据可用于定位，但修复通过仍需修复后的浏览器回归。
            该规则不禁止必要安全验证，也不能用“节省时间”理由跳过证据不足的高风险缺陷。

            # 一、一次接收材料，冻结本轮任务
            1. 先读 html_acceptance_report.md、范围与证据索引、当前 HTML，按问题定位读取直接相关的需求和证据。
               需求尚未建立可用索引时读取并建立一次，之后只补读必要片段；不要无差别打开全部截图和所有 JSON 明细。
            2. 检查报告是否自相矛盾或有测试误判。只有证据不足的 Issue 才先局部复现，不再执行一轮完整初验。
               错误密码仍登录、权限判断等重要结论用明确断言确认，不能仅凭页面截图作结论。
            3. 固定本轮 Issue 清单，给每项建立：根因组、受影响组件/页面、拟改位置、回归用例。
               BLOCKED/NOT_TESTED 是验证状态，不自动成为实现缺陷；已有组件缺少必需行为仍必须作为缺陷处理。
               第一阶段遗漏的独立新问题记录为后续项，不无限加入本轮；本次修改引入的回归和阻断本轮验证的问题纳入处理。
               新发现的严重安全或数据破坏风险必须醒目标出，不因不纳入本轮而隐去或标通过。

            # 二、按根因批量修改，不逐问题重复试跑
            1. 优先处理 P0/P1，其次 P2/P3。相同根因影响多个页面时先修公共来源，再统一验证所有受影响实例。
               检查公共高度、overflow、固定底栏、表格宽度及共享样式，但必须用证据确认共同根因，不凭报告猜测批量改动。
            2. 保留已经正确的 DOM、视觉和交互，用最小必要改动解决问题，不为形式统一重写整页或新增无关架构层。
               GlobalStore/Router 要求继续有效：确认确有重复正式实体或独立 history 才进行对应整合；已正确的统一机制不重构。
               公共样式统一以已有合理实现为准；业务 variant 保留，不为统一而改变页面专属功能。
            3. 同实体字段从一个权威来源读取，统计按同口径派生；不能 hardcode 跨页值、直接改 DOM 假装保存、用 toast 冒充数据后果。
               导航参数、草稿与返回状态、权限守卫、校验、防重入、事务回滚和弹窗生命周期只修改问题及其必要依赖涉及的部分。
            4. 本次仅允许修改指定 HTML；需求与共享 JSON 保持只读，与末尾文件权限一致。
               若缺陷必须修改共享 JSON 才能解决，记录具体字段、理由和 BLOCKED，不擅自修改，也不得用各页面硬编码绕过。
            5. 原抽屉迁入居中弹窗或已有详情页时保留其业务能力；不得删组件、永久禁用、删分支、降低测试断言或隐藏问题来过关。
            6. 同根因组的修改先一次完成，再运行该组回归；不要每改一行 CSS、每个按钮或每个关联 Issue 就重复跑完整流程。

            # 二补充、跨页面协调性修复与验证
            1. 沿用第一阶段的语义/层级/variant/状态分组和已确认基准，处理尺寸、字号、字重、行高、颜色、间距、圆角、边框、阴影及对齐差异。
               修复前用已有清单识别同组全部实例，不能只改报告示例页；优先修改确有问题的共享样式或变量，必要时删除冲突局部覆盖。
               没有现成公共机制时做最小必要修改，不为统一样式重建组件框架或重写页面。
            2. 只统一缺少业务理由的差异，保留语义配色、文案宽度、内容高度和响应式变化；不得统一掉危险态、禁用态、错误态等必要区分。
               不随意更换颜色体系、缩小字体或隐藏内容；保留点击事件、权限、路由、表单校验和业务状态。
            3. 将修改过的公共规则及全部依赖实例纳入受影响范围回归，在已有页面遍历时批量重新采集相同属性并与基准比较。
               验证同层级文字、同类组件、整体内容边界与对齐；检查没有新增裁切、溢出、遮挡或不合理留白。
               改动涉及交互状态样式时，真实触发并验证适用状态；独立覆盖单独验证，共享实现可代表验证并说明覆盖边界。
            4. 使用已有首次测量和本次有效测量生成修复前/后差异摘要；不能以 class 名相同替代实际渲染结果，也不能用源码推测判 PASS。
               如后续变更影响已验证样式，该结果失效并重测；否则复用本次有效结果，不为报告单独再跑视觉遍历。
               只对视觉异常、确有必要的改动对照及整体协调性疑点截图，沿用原有轮次和截图限制。

            # 三、复用测试，只运行必要范围
            1. 从 html_repair_handoff.json 逐项读取既有复现/回归命令，直接复用第一阶段脚本、fixture 和稳定测试 ID，只调整合法 UI 改动导致失效的定位器，保留业务断言。
               不重写等价框架，不对所有组件重新创建独立上下文；维持一个服务和浏览器，按独立写操作流程隔离状态。
            2. 回归范围由真实代码依赖和影响范围确定，不能只按修改文件名判定。
               局部组件改动：该组件相关成功/失败/取消路径，以及直接受影响页面和数据。
               公共 CSS/组件改动：所有使用该规则的页面和实例做布局及主要操作回归。
               GlobalStore/Router/共享权限/统一事务机制改动：必须扩大到依赖它的全部页面、相关写入链和权限/导航场景。
               即使修改在一个 HTML 文件内，也要按内部依赖判断；不能因文件单一就总是全量，也不能漏掉全局影响。
            3. 每个根因组验证：原缺陷消失，已有组件功能正常，写操作后相关 UI/统计更新，无新运行错误或遮挡。
               第一阶段必要的合法提交、校验失败、取消/重置和跨页核对继续执行于受影响表单，不重跑无关深度异常组合。
            4. 所有修改完成后进行一次最终回归批次：全部页面基础进入/导航/运行错误检查，加受影响范围的完整相关测试。
               全页面基础检查不能当作所有功能通过；无关页面不再次逐字段、逐分支穷举测试。
               根因组在最后一次相关修改后已有有效结果且后续变更不影响它时，最终批次可汇总该结果，不重复执行。
               若依赖发生变化，则旧结果失效，必须重测相关用例；记录测试时的代码版本与依赖判断。
            测试执行必须具备可诊断的退出码：不要把多个较长 Playwright 脚本放进单个受工具默认 120 秒限制的 shell 调用。
            分批短运行，每个命令只覆盖一个有限业务流程或可控的小组；确需长流程时显式设置工具允许的较长等待时间，
            并使外层等待大于脚本自身超时。逐脚本写入耗时、退出码、失败断言与证据路径，不使用无 pipefail 的管道或只看 tail 输出判断成功。
            对 Playwright 预期可快速出现的元素设置合理的显式等待，并等待真实状态；若超时，先核对页面/选择器/遮挡，
            不把 30 秒默认超时重复消耗在同一错误定位器上。不得以盲目缩短等待牺牲慢操作的正确性。
            最终回归依赖矩阵先确定后运行一次；局部补修只重跑其变化依赖，公共 CSS/Store/Router 变化仍覆盖全部受影响页面。
            同一无变化的脚本结果按代码版本与输入哈希复用，不为不同报告章节或截图再次执行。
            5. 只对视觉改动页和已确认视觉问题截图对照；DOM 断言足够的功能步骤不截图。
               同一状态复用一张图；二维码仅在其渲染或载荷受影响时重新采集解码。

            # 四、轮次限制与停止条件
            1. 本轮最多：一轮按根因批量修复与局部验证、一轮最终回归、一次针对回归失败项的补修和受影响复测。
               不因补修发现新问题就重新启动全量验收或开启无限修复循环；补修涉及全局依赖仍须覆盖其真实影响范围。
            2. 同一测试阻塞最多一次有针对性的排查/重试；没有可用前置条件就记录 BLOCKED/NOT_TESTED，不反复导航等待。
            3. 轮次用尽仍未修复的问题记录 NOT_FIXED/PARTIALLY_FIXED/BLOCKED，输出原因和剩余风险后结束。
               范围内问题不能因此移出分母；有失败、阻塞或未测不能伪报 PASS。
            4. 不为完美报告不断重新截图、改写所有章节或全量运行；报告从本次证据一次汇总。

            # 五、报告、覆盖来源和结果 JSON
            1. 生成 html_fix_report.md：Issue、严重度、根因组、修改位置、修复说明、需求引用、局部/最终回归、剩余问题。
               修复结果为 FIXED/PARTIALLY_FIXED/NOT_FIXED/BLOCKED；误报纠正另附证据说明，不机械修复误报。
            2. 生成 html_acceptance_report_after_fix.md：本次改动摘要、页面基础检查、受影响范围回归、剩余缺陷及覆盖限制。
               测试证据必须区分：本阶段实际执行；本阶段局部验证后依赖未变的有效结果；第一阶段历史结果；未验证。
               第一阶段历史 PASS 只作背景参考，未在修复后执行的必需场景按 not_tested 计，不能冒充本阶段完整认证。
               记录每项的稳定测试 ID 和证据路径，避免同一失败在多个章节重复计数。
            3. 报告正文保留异常和汇总；正常几何、样式、实体与逐步日志保存在已有结构化证据文件。
               不重复罗列全部正常字段，不为生成最终报告再次运行测试。
            4. 必须写入 {save_dir / 'html_acceptance_result.json'}，JSON 对象包含 status、failed、blocked、not_tested。
               三个计数为非负整数，按固定范围内去重的测试项统计；未执行的必需深度场景和未复验的历史项不能漏计。
               status 只使用 PASS、PASS_WITH_MINOR_ISSUES 或 FAIL。
               只有范围内所有必需检查都有修复后的有效通过证据，且三个计数全部为 0，才允许 PASS。
               存在失败、阻塞或未测试项时使用 FAIL，报告解释已修复内容与验证边界；不得为满足外部校验器而伪造结果或继续无限循环。
            5. 输出材料读取、问题定位、修改、局部测试、最终回归、补修、截图及报告生成的计时与阶段总耗时。
               截图计时为测试内子项，不重复累加；无法准确拆分的模型工作说明限制，不能把脚本时间当整个阶段时间。


            # 耗时日志输出协议
            在步骤真正开始时即时输出并刷新 [STEP_START]，真正完成时输出并刷新 [STEP_END]。
            禁止在最后集中补印旧步骤标记，也不要重复输出同一条已记录的 [TIMING]；尚未执行或因中断未结束的步骤不能伪称完成。
            如需归纳步骤，只在最终报告列摘要，不再使用 START/END 标记冒充实时计时。
            对可用脚本实际计时的步骤，额外单行输出 [TIMING] 后接 JSON 对象，字段为 step、elapsed_seconds、measurement。
            step 为具体步骤名，elapsed_seconds 为实际测得的非负秒数，measurement 固定为 measured。
            用脚本单调时钟测量脚本准备/执行、局部复测、截图与报告生成等能可靠计时的部分；无法实际测得的模型分析时间只输出步骤标记，不编造秒数。
            截图时间可能包含在测试总时间中，不能把所有细项直接累加成阶段总时间。
            计时行必须实际输出到控制台，不仅写在报告里，不要只在最终答案重复一个总数。
        """).strip()
    
        prompt = PROMPT+'\n'+f'交互需求文档路径:{requirement_file}\n共享数据路径:{shared_context_path}\nHTML路径:{html_path}\n报告及测试产物目录:{save_dir}\n验收报告路径:{save_dir / "html_acceptance_report.md"}\n业务输入仅限上述需求文档、共享数据和 HTML；允许读取本次验收报告及测试证据、修改指定 HTML，并在产物目录生成测试脚本、证据、html_fix_report.md、html_acceptance_report_after_fix.md 和 html_acceptance_result.json。禁止修改需求文档或访问无关文件。'
        if tool == 'opencode':
            cmd = [OPENCODE_CMD, "run", "--auto","--dir",CWD,"-m", DEEPSEEK_V4_PRO, '--variant', 'max',"--dangerously-skip-permissions", prompt]
        else:
            cmd = [
                CLAUDE_BINARY,
                'exec',
                '-m', REPAIRE_MODEL,
                '-c', f'model_reasoning_effort={REPAIRE_MODEL_EFFECT}',
                '-C', CWD,
                '-c', 'project_root_markers=[]',
                '--dangerously-bypass-approvals-and-sandbox',
                prompt
            ]
        with _timed_phase('stage_2', '第二阶段：修复与回归') as _stage:
            _stage_clock = time.perf_counter()
            process = subprocess.Popen(
                cmd,
                cwd=save_dir,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,

            )

            _stage['pid'] = process.pid
            _stage['_started_monotonic'] = _stage_clock
            _stage['_last_output_monotonic'] = _stage_clock
            _save_summary()
            with open(_stage['log_path'], 'a', encoding='utf-8') as _output_log:
                for line in process.stdout:
                    _record_line(_stage, _output_log, line)

            _stage['returncode'] = process.wait()
            # if _stage['returncode'] != 0:
                # raise RuntimeError('HTML 修复命令失败')
        # with _timed_phase('final_validation', '最终产物校验'):
            # validate_stage_outputs('repair', save_dir)
    except BaseException as exc:
        _summary['status'] = 'INTERRUPTED' if isinstance(exc, KeyboardInterrupt) else 'ERROR'
        _summary['error'] = f'{type(exc).__name__}: {exc}'
        raise
    else:
        _summary['status'] = 'COMPLETED'
    finally:
        _summary['ended_at'] = _now()
        total = time.perf_counter() - _run_started
        measured = sum(item.get('elapsed_seconds', 0) for item in _summary['phases'])
        _summary['other_seconds'] = round(max(0, total-measured), 3)
        _event('run_end', status=_summary['status'], elapsed_seconds=round(total, 3))
        _save_summary()
        _display = ['HTML 验收与修复耗时', f'运行状态：{_summary["status"]}',
                    f'总耗时：{_summary["elapsed_seconds"]:.3f} 秒', '']
        for item in _summary['phases']:
            _display.append(f'{item["label"]}：{item.get("elapsed_seconds", 0):.3f} 秒；{item["status"]}')
            for detail in item['reported_timings']:
                _display.append(f'  子进程报告 / {detail["step"]}：{detail["elapsed_seconds"]:.3f} 秒（可能与其他细项重叠）')
        _display.extend(['', f'其他准备/日志开销：{_summary["other_seconds"]:.3f} 秒',
                         'COMPLETED 只表示调用及校验正常返回，业务验收结论以验收报告为准。',
                         'gap 是两行输出接收时间差，包含 CLI 缓冲影响，不能等同于某步骤耗时。',
                         '正常退出或 Python 异常时会完成汇总；kill -9/断电可能只保留已落盘记录。'])
        (_log_dir / 'timing_summary.txt').write_text('\n'.join(_display)+'\n', encoding='utf-8')
        print('\n'.join(_display), flush=True)
        print(f'[计时] 详细日志：{_log_dir}', flush=True)

 
 
prompt_ruanzhu = """
  1、使用software-copyright-materials skill，参考 docs/superpowers、麝群繁育遗传数据分析系统_交互需求文档.xml、htmls_codex/merge.html、workspace 生成软著材料
  2、你不需要生成代码材料
  3、截图保存在 “截图“文件夹下，直接插入到操作手册中，图片和图片下的名称水平居中。
  4、操作手册中禁止出现单页html字眼，如果存在冲突地方，以htmls/merge.html为准，操作手册中禁止出现merge.html中不存在的内容和功能
  5、采用二级目录结构，和merge.html的导航栏保持一致
  6、不要 “相关文档” 章节
  7、如果使用【】，则【】内的文字和组件的文本必须完全一致
"""

prompt_backend = """
使用 business-specific-coding skill，根据 docs/superpowers、htmls_codex/shared_context.json、麝群繁育遗传数据分析系统_交互需求文档.xml、htmls_codex/merge.html实现前端代码，如果存在冲突以htmls_codex/merge.html为准，必须实现merge.html中的所有功能，代码保存到workspace,注意演示数据不要出现在代码中，
这是一个生产级别的系统，不是demo。对于htmls_codex/merge.html中的固定文本，实现的前端代码中必须与其保持完全一致，固定文本的定义为：不随着用户输入、用户操作和后端api而改变的文本

""" 

prompt_frontend = '''
请在当前项目原有的 htmls/merge.html 上进行改造，将页面从 mock 数据驱动改为通过 HTTP API 获取和提交业务数据。以下要求以修改前的 merge.html 为基准。

【交付形式：保留单个 HTML】
最终可运行的页面产物仍为单个HTML文件，页面自身的样式和业务脚本继续内嵌在该文件中。基于原文件进行必要修改，不重写为另一套页面，不拆分为多个 HTML、CSS、JavaScript 或组件文件，不新建前端工程，不引入新的前端框架或构建流程。原有静态资源保持适用的引用或内嵌方式。API 契约、修改前基线及核对说明可以独立保存，但不得成为页面运行依赖。

【强制要求：修改前后固定文本必须完全一致】
修改后的前端中，所有原有固定文本必须与修改前的 htmls/merge.html 完全一致，逐字、逐字符保留。此要求是强制验收条件，不能以功能正常、API 接入完成、含义相同或界面相似代替。任何原有固定文本或固定片段发生改写、遗漏、增删或位置错配，均视为未通过验收，必须修正后再交付。

一、实施范围与目标
1. 本次只实现前端改造，不修改或实现后端代码、数据库及后端业务逻辑。后端由我在前端改造完成后，根据修改好的 merge.html 及前端 API 契约自行实现。
2. 阅读项目约定、merge.html 及相关前端代码，理解并沿用原有页面组织和运行方式，在单个 HTML 内复用或实现适用的请求封装与配置。无需先确认后端是否已有接口，不得因后端尚未实现而停工、删减功能或永久禁用操作。
3. 根据页面现有功能设计并实现完整的前端 API 调用，同时输出与实际调用一致的 API 契约，供我适配后端。新增的路径和字段属于本次设计约定，不应描述为已经存在或已经联调通过的后端接口。
4. 删除最终 merge.html 内嵌逻辑中的 mock 数据、演示业务记录、随机生成的业务数据、模拟请求和 mock 回退逻辑，包括未被调用的演示常量和预填业务样例。要求清理源码本身，不能仅让这些数据不再显示。
5. 保留原有页面结构、布局、样式、功能入口和交互方式，只进行 mock 清理、API 数据获取与提交、数据绑定、必要状态处理及代码注释清理所需的修改，不进行无关重构或工程化拆分。
6. 本次交付的自有前端代码不保留代码注释。清除改造范围内已有的 HTML、CSS 和 JavaScript 注释，不新增代码注释；必要说明写入独立文档，不放在前端源码中。清理注释不得破坏字符串、模板内容或程序语义。

二、固定文本的定义与判定方法
固定文本的定义：不随着用户输入、用户操作和后端 API 发生改变的文本。

根据文本的业务用途和实际来源判断其是否动态，不得仅凭它位于按钮、表头、下拉框或图表中就认定为固定文本。不预先枚举固定文本类型，也不按控件类型一律判定。

具体判定规则：
1. 以修改前页面的业务含义和数据流为依据，追溯文本的来源、赋值逻辑及变化条件，区分由业务数据决定的内容与前端预先定义的界面文案。不得通过修改文本来源或将其迁移到 API，重新将原有固定文本解释为动态数据以规避保护要求。
2. 判断是否动态，应考虑真实业务中内容是否会随输入、操作或 API 数据变化。当前 mock 数据被写死、暂时只有一个取值或当前画面未变化，不代表该内容属于固定文本。
3. 判断对象是文字内容。文本的显示、隐藏或所在状态发生切换，不代表原有文字本身可以改写。预先定义的各状态文案分别保留原文，仅按实际状态切换显示。
4. 同一控件内可以同时存在固定文本与动态数据，必须按实际内容逐段判断。混合文本只允许动态值变化，其余固定片段及片段与动态值之间的原有分隔必须完全保留。
5. 对动态内容按其真实业务来源获取或计算；对判定为固定的原有文本执行逐字符保护。不得将演示业务数据作为固定文案保留，也不得将固定文案作为 mock 数据删除。

三、固定文本的全量保护要求
1. 以开始修改前的 htmls/merge.html 为唯一原始文案基准，在首次修改前保存独立基线。后续不得覆盖基线，也不得使用已修改的版本作为“修改前”进行比对。
2. 对 merge.html 内嵌的全部页面及其关联前端逻辑进行全量检查。无论文本存储在何处、通过何种方式生成、是否默认显示，只要按上述规则判定为固定文本，均纳入保护范围；不能用预先列出的类型清单代替实际判定。
3. 修改后的每一处原有固定文本及固定片段，必须与修改前对应位置的原文完全一致，逐字、逐字符保留。即使原文存在错字、用词不统一或表达不顺，也不得擅自修改。不得改写、润色、纠错、缩写、翻译或替换同义词。
4. 完全一致包括大小写、符号、标点、全角/半角、空格和原有显式文本换行，也包括固定片段与动态值交界处的原有分隔。响应式布局自然产生的折行不属于文本内容变化。
5. 一致性以文本在对应控件、页面区域和交互状态中的实际显示内容或辅助功能读取内容为准，不要求 HTML 或 JavaScript 的代码写法完全相同。
6. 不得使用 API 返回值覆盖受保护的原有固定文案。需要根据业务状态选择预设文案时，沿用原有文案及其对应关系。
7. 不得通过删除功能、隐藏文字、将原文放入注释或无关位置来规避一致性要求。保留文字与原控件、原页面区域及相应交互状态之间的对应关系。

四、前端 API 实现与契约
1. 按页面实际存在的列表、详情、统计、图表、筛选、搜索、排序、分页、新增、编辑、删除、导入导出等功能逐项处理，不遗漏隐藏区域或弹窗中的操作。
2. 为需要服务端数据或业务处理的功能实现真实 HTTP 请求。展开弹窗、切换可见区域等纯界面操作无需强行增加接口。
3. 在 merge.html 内集中管理 API 基础地址及请求配置，避免在不同脚本逻辑中散落硬编码地址。复用适用的请求封装和已有鉴权配置，不为此拆出独立业务脚本或配置文件。
4. 设计一致、可实现的请求和响应结构，明确字段类型、必填性、可空性、日期格式、分页起始页、总条数、筛选和排序参数、状态代码及错误结构。
5. 正确绑定响应数据；提交、删除等业务操作应在接口确认成功后更新页面，不得以本地数组修改或模拟延时冒充操作成功。
6. 保留必要的数据格式转换、前端输入校验和界面计算，不得编造业务数据或用随机数补齐图表。
7. 输出 frontend-api-contract.md，按功能列出请求方法、路径、参数、请求体、响应结构、错误约定及对应页面区域。契约必须与最终代码一致，明确标注这是供后端实现的约定。
8. 契约中的结构示例仅用于说明，不能作为页面初始化数据或失败回退数据被运行时代码加载。

五、演示数据清理与页面状态
1. 清理范围为最终 merge.html 的全部相关源码和内嵌数据，不仅限于当前执行路径。修改前的独立基线用于核对，不作为页面资源加载；不涉及删除数据库数据或其他无关文件。
2. 清除演示表格记录、演示详情、预填业务样例、硬编码统计结果、图表样本、随机生成数据及浏览器存储中的演示数据读取或初始化逻辑。需要从后端获取的具体业务值不得硬编码在前端源码中，也不得保留在初始 HTML、属性值、默认值或失败回退值中。
   例如“周砚秋”属于当前 mock 的用户姓名，修改后的前端源码中不得继续保留这个姓名作为业务数据。当前用户姓名必须读取 API 响应的相应字段；前端只保留字段读取、数据绑定及状态处理逻辑。运行时显示 API 返回的姓名不等于在源码中硬编码姓名。
3. 不得将 mock 搬到其他前端文件、静态 JSON、浏览器存储或模拟服务中继续使用。
4. 依据业务用途和实际来源区分演示业务数据与前端正常运行所需的界面定义、配置及逻辑，不得以清理 mock 为由误删后者。固定文本是否保留统一遵循第二、三部分的判定和保护规则。
5. 分别处理首次加载、加载中、成功有数据、成功但无数据、请求失败和提交中等实际需要的状态。
6. 后端尚未实现或请求失败时，显示正确的失败状态，不回退为演示数据，不伪装为成功或“没有业务记录”。
7. 未取得统计值时，不得用 0 冒充真实统计结果；API 确实返回 0 时才作为业务统计值展示。
8. 无数据或请求失败时仍保留页面结构及对应状态下应显示的固定文本，不得以数据未返回为由删减或改写文案。
9. 优先复用原有状态文案。确需新增提示时，单独列明新增文字及用途，不得改写受保护的原有固定文本。

六、验收与交付
1. 建立“页面区域／控件／状态—修改前固定文本或固定片段—修改后对应文本—比对结果”的清单，对照首次修改前保存的基线逐项核对。覆盖 merge.html 内嵌的全部页面，以及其他标签页、弹窗、折叠区域、提示状态和脚本动态生成的文案。不能只核对默认页面或比较去重后的文字集合。
   固定文本验收标准：原有固定文本及固定片段内容差异为 0，遗漏为 0，原控件与文案对应关系错误为 0。发现差异必须修复并重新核对；未完成核对的项目须明确标为未验证，不得声称“完全一致”。新增提示单独列明，不得用新增提示替换原有固定文本。
2. 对混合文本逐段核对，确认变化仅发生在动态值中，所有固定片段及原有分隔均与修改前完全一致。判定依据须能追溯到修改前的业务用途和实际来源，不得仅凭控件类型或代码中的常量形式作出判断。
3. 检查最终 merge.html 的全部源码和内嵌数据，确认硬编码演示业务数据、未使用的演示常量、模拟成功逻辑和 mock 回退路径均已移除。必须检查源码残留，不能仅以页面没有显示演示数据作为通过依据。同时检查改造范围内的自有前端代码，确认未保留或新增代码注释。
4. 对单个 HTML 执行适用的语法检查、静态检查及浏览器页面检查，核对实际请求方法、地址、参数、响应处理与 API 契约一致。按相同视口和对应交互状态对照修改前页面，验证布局、样式、固定文案和交互的一致性；业务数据值及正常加载、空数据、失败状态按真实状态处理，不要求复现演示数据。不得仅因产物仍是单个 HTML 就声称一致性已经通过验证。
5. 如使用隔离的测试响应验证成功、空数据或异常场景，测试数据不得进入页面运行时产物，且不能将该验证称为真实后端联调。
6. 后端尚未实现不构成本次前端工作的阻塞项。完成前端可验证的工作，准确说明验证范围和待后端实现后的联调事项。
7. 交付修改后的 html并另保存为 htmls/merge1.html 和独立的 frontend-api-contract.md。最终说明各功能对应的 API 契约、移除的 mock 逻辑、固定文本比对结果、必要的新增提示、页面一致性检查及其他验证结果，并提供该 HTML 的访问方式和 API 基础地址配置说明。不得以一个需要安装依赖或构建后才能访问的前端工程代替单个 HTML 交付。

请先完成必要检查，再编写代码 并输出独立 API 契约，不要只提供方案。最终页面仍为单个 HTML，不进行工程化拆分。不要实现后端，也不要因后端尚未实现而停止前端改造。所有原有固定文本及固定片段，修改前后必须逐字、逐字符完全一致。
整个任务只新增了htmls/merge1.html一个文件，禁止修改任何已有文件
'''


def main():
    requirement_file =  os.path.join(PARENT_DIR, '田间智能浅埋微灌节水灌溉管控系统_交互需求文档_.xml')

    screenshot_dir = os.path.join(PARENT_DIR, 'screenshots')
    html_dir = os.path.join(PARENT_DIR, 'htmls')
    merge_path = os.path.join(html_dir, 'merge.html')
    context_path = os.path.join(html_dir, 'shared_context.json')
    # merge_path = os.path.join(PARENT_DIR, 'merge_bk1.html')
    jietu_dir = os.path.join(PARENT_DIR, '截图') 
    cate = 'web'
    if cate not in ('web', '手机app', 'windows应用'):
        raise ValueError(f'不支持的界面类型：{cate}')

    import pdb
    pdb.set_trace()
    # get_requirement('实验室样品全生命周期管理WEB_交互需求文档_模板_V2.1.xml', '麝群繁育遗传数据分析系统', './', cate=cate)
    prepare_shared_context(requirement_file, html_dir)
    # get_web_screenshots(requirement_file, context_path, screenshot_dir)
    # get_htmls_from_screenshot(requirement_file, screenshot_dir, html_dir, cate)
    merge_htmls(requirement_file, html_dir, cate=cate,tool='opencode')
    check_and_repaire_html(requirement_file, merge_path, cate=cate, tool='opencode')
    # check_and_repaire_html(requirement_file, merge_path, cate=cate, tool='codex')

    screenshot_html(merge_path, jietu_dir, cate=cate,tool='opencode')


if __name__ == '__main__':
    main()


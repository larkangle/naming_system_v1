import asyncio
from dotenv import load_dotenv
from claude_agent_sdk import (
    ClaudeSDKClient, 
    ClaudeAgentOptions, 
    ResultMessage, 
    AssistantMessage, 
    TextBlock
)
from agent_configs import get_subagents_config, get_moderator_prompt
from data_models import FinalReport

# Load environment variables
load_dotenv()

async def run_naming_session():
    # 1. Get User Input
    print("--- 欢迎来到全能专家取名研讨会 ---")
    print("我们需要一些基本信息来启动会议。")
    
    family_name = input("请输入姓氏 (例如: 李): ")
    gender = input("请输入性别 (男孩/女孩): ")
    birth_info = input("请输入出生信息 (例如: 2024年5月20日 早上8点，用于算命和星座): ")
    wishes = input("请输入您的期望 (例如: 希望聪明、健康，避免生僻字): ")
    
    user_prompt = f"""
    用户需求：
    姓氏：{family_name}
    性别：{gender}
    出生信息：{birth_info}
    期望：{wishes}
    
    请按照主持人流程开始会议。
    """

    # 2. Configure the Agent
    subagents = get_subagents_config()
    system_prompt = get_moderator_prompt()
    
    options = ClaudeAgentOptions(
        model="MiniMax-M2.1",
        system_prompt=system_prompt,
        agents=subagents,
        allowed_tools=["Task"], # Enable delegation
        setting_sources=["project"], # Load CLAUDE.md
        output_format={
            "type": "json_schema",
            "schema": FinalReport.model_json_schema()
        }
    )

    print("\n--- 会议开始，专家们正在激烈讨论中 (这可能需要几分钟) ---\n")

    # 3. Run the Agent with Session Management
    async with ClaudeSDKClient(options=options) as client:
        try:
            # Initial Request with auto-retry
            await run_with_retry(client, user_prompt)

            # Follow-up Loop
            while True:
                follow_up = input("\n对结果满意吗？(输入 'exit' 退出，或输入新的要求): ")
                if follow_up.lower() in ['exit', 'quit', 'q']:
                    break
                
                print("\n--- 专家们正在根据您的反馈调整 ---\n")
                await run_with_retry(client, follow_up, allow_user_nomination=False)

        except Exception as e:
            print(f"发生错误: {e}")

async def process_response(client: ClaudeSDKClient, stop_after_phase: int = None) -> int:
    """
    处理流式响应，检测阶段标记，返回完成的阶段数。
    返回值：0=未开始, 1=第一轮完成, 2=第二轮完成, 3=全部完成
    
    参数：
        stop_after_phase: 如果指定，在检测到该阶段完成标记后立即返回（用于用户提名窗口）
    """
    current_phase = 0
    
    async for message in client.receive_response():
        # 处理 AssistantMessage
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    
                    # 先打印回复内容
                    print(f"\n[回复]: {text}")
                    
                    # 检测阶段标记并在之后打印分隔线
                    if "【第一轮结束】" in text:
                        current_phase = 1
                        print("\n" + "=" * 50)
                        print("📋 提名阶段完成，进入质询阶段...")
                        print("=" * 50)
                        # 如果需要在第一轮后停止，立即返回
                        if stop_after_phase == 1:
                            return current_phase
                    elif "【第二轮结束】" in text:
                        current_phase = 2
                        print("\n" + "=" * 50)
                        print("🗳️ 质询阶段完成，进入决选阶段...")
                        print("=" * 50)
                        if stop_after_phase == 2:
                            return current_phase
                    elif "【第三轮结束】" in text:
                        current_phase = 3
                        print("\n" + "=" * 50)
                        print("🏆 决选完成，生成最终报告...")
                        print("=" * 50)

        # 处理成本追踪
        if isinstance(message, ResultMessage):
            print(f"\n[System] 本轮耗时: {message.duration_ms}ms")
            if message.total_cost_usd:
                print(f"[System] 本轮成本: ${message.total_cost_usd:.4f}")

        # 处理结构化输出
        if hasattr(message, 'structured_output') and message.structured_output:
            result = FinalReport.model_validate(message.structured_output)
            print_report(result)
    
    return current_phase


async def run_with_retry(client: ClaudeSDKClient, initial_prompt: str, max_retries: int = 2, allow_user_nomination: bool = True):
    """执行查询并在流程不完整时自动重试，支持用户提名"""
    retry_count = 0
    user_nominated = False  # 标记是否已经处理过用户提名
    
    # 首次执行 - 如果允许用户提名，在第一轮结束后停止
    await client.query(initial_prompt)
    if allow_user_nomination:
        current_phase = await process_response(client, stop_after_phase=1)
    else:
        current_phase = await process_response(client)
    
    # 第一轮结束后，允许用户追加名字
    if current_phase == 1 and allow_user_nomination and not user_nominated:
        user_nominated = True
        print("\n" + "-" * 50)
        print("💡 现在您可以追加自己想到的名字！")
        print("   格式：名字1, 名字2, 名字3 (用逗号分隔)")
        print("   或直接按回车跳过")
        print("-" * 50)
        
        user_names = input("请输入您的名字创意: ").strip()
        
        if user_names:
            # 解析用户输入的名字
            names_list = [n.strip() for n in user_names.replace("，", ",").split(",") if n.strip()]
            if names_list:
                names_str = ", ".join(names_list)
                print(f"\n✅ 已收到您的提名：{names_str}")
                print("--- 专家们将把这些名字纳入质询评分 ---\n")
                
                # 将用户提名发送给主持人
                user_nomination_prompt = f"""
用户追加了以下名字，请将这些名字加入候选列表（标记提案人为"用户提名"），然后继续进行质询阶段：

用户提名的名字：{names_str}

请继续执行阶段2（质询）和后续流程。
"""
                await client.query(user_nomination_prompt)
                current_phase = await process_response(client)
        else:
            print("\n--- 跳过用户提名，继续进行质询阶段 ---\n")
            # 继续执行后续流程
            await client.query("请继续完成剩余流程，从质询阶段开始。")
            current_phase = await process_response(client)
    
    # 检查是否需要重试
    while current_phase < 3 and retry_count < max_retries:
        retry_count += 1
        phase_names = {0: "提名", 1: "质询", 2: "决选"}
        incomplete_phase = phase_names.get(current_phase, "未知")
        
        print(f"\n⚠️ 流程未完成（停在{incomplete_phase}阶段），自动重试 ({retry_count}/{max_retries})...")
        print("-" * 40)
        
        await client.query("请继续完成剩余流程，从上次中断的地方继续。")
        current_phase = await process_response(client)
    
    # 最终检查
    if current_phase < 3:
        print(f"\n❌ 警告：流程经过 {max_retries} 次重试后仍未完成，请检查主持人 prompt 或手动继续。")

def print_report(report: FinalReport):
    print("\n" + "="*50)
    print("🎉 最终取名报告 🎉")
    print("="*50)
    print(f"\n会议总结:\n{report.summary}\n")
    
    print("-" * 30)
    print("🏆 推荐名单 (按得分排序)")
    print("-" * 30)
    
    for i, item in enumerate(report.ranked_names, 1):
        print(f"\n第 {i} 名: 【{item.name_info.name}】 (总分: {item.total_score})")
        print(f"   拼音: {item.name_info.pinyin}")
        print(f"   寓意: {item.name_info.meaning}")
        print(f"   提案人: {item.name_info.proposer}")
        print(f"   专家评审:")
        for critique in item.critiques:
            print(f"     - [{critique.critic_role}] ({critique.score}分): {critique.comment}")

if __name__ == "__main__":
    asyncio.run(run_naming_session())

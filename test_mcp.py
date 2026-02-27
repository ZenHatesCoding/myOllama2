import asyncio
from mcp import MCPManager, NewsMCP


async def test_news_mcp():
    print("=== 测试新闻MCP功能 ===\n")
    
    mcp_manager = MCPManager()
    
    # 不配置API密钥，使用演示数据模式
    news_mcp = NewsMCP()
    mcp_manager.register_mcp(news_mcp)
    
    test_queries = [
        "获取头条新闻",
        "获取今天的科技新闻",
        "搜索关于人工智能的新闻",
        "获取最新的体育新闻",
        "获取财经新闻"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"用户输入: {query}")
        print('='*60)
        
        result = await mcp_manager.detect_intent_and_execute(query)
        
        if result:
            if result.get("success"):
                print(f"✓ 工具调用成功: {result.get('tool_name')}")
                print(f"\n返回内容:\n{result.get('formatted_text', '')}")
            else:
                print(f"✗ 工具调用失败: {result.get('error')}")
        else:
            print("✗ 未检测到需要使用工具")
        
        print('='*60)
    
    print("\n=== 测试完成 ===")
    print("\n提示: 要获取真实新闻，请申请聚合数据API密钥:")
    print("  1. 访问 https://www.juhe.cn/")
    print("  2. 注册账号")
    print("  3. 申请'新闻头条'API")
    print("  4. 在代码中配置API密钥: NewsMCP(api_key='your_key')")


if __name__ == "__main__":
    asyncio.run(test_news_mcp())

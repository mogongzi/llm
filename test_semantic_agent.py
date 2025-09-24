#!/usr/bin/env python3
"""
Test the new semantic SQL analysis approach with diverse real-world queries.
"""
import sys
import asyncio
from pathlib import Path

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from agents.tools.semantic_sql_analyzer import SemanticSQLAnalyzer, QueryIntent
from agents.tools.enhanced_sql_rails_search import EnhancedSQLRailsSearch


class TestQuery:
    def __init__(self, sql: str, expected_intent: QueryIntent, description: str):
        self.sql = sql
        self.expected_intent = expected_intent
        self.description = description


# Real-world test queries covering diverse scenarios
TEST_QUERIES = [
    TestQuery(
        sql='SELECT 1 AS one FROM "line_items" WHERE "line_items"."cart_id" = $1 LIMIT 1',
        expected_intent=QueryIntent.EXISTENCE_CHECK,
        description="Existence check with foreign key (your example)"
    ),

    TestQuery(
        sql='SELECT COUNT(*) FROM users WHERE users.active = true',
        expected_intent=QueryIntent.COUNT_AGGREGATE,
        description="Count active users"
    ),

    TestQuery(
        sql="INSERT INTO audit_logs (uuid, member_id, operation) VALUES ($1, $2, 'CREATE')",
        expected_intent=QueryIntent.DATA_INSERTION,
        description="Audit log insertion"
    ),

    TestQuery(
        sql='UPDATE products SET updated_at = NOW() WHERE id IN (1, 2, 3)',
        expected_intent=QueryIntent.DATA_UPDATE,
        description="Bulk product update"
    ),

    TestQuery(
        sql='SELECT users.* FROM users INNER JOIN memberships ON users.id = memberships.user_id WHERE memberships.active = true ORDER BY users.created_at DESC LIMIT 10',
        expected_intent=QueryIntent.DATA_RETRIEVAL,
        description="Complex join with ordering and limit"
    ),

    TestQuery(
        sql="SELECT 1 FROM audit_logs WHERE audit_logs.uuid = x'6452594435704865365a616d4c473279654f456f4b41' LIMIT 1",
        expected_intent=QueryIntent.EXISTENCE_CHECK,
        description="UUID existence check with hex encoding"
    ),

    TestQuery(
        sql="SELECT aggregated_content_views.* FROM aggregated_content_views WHERE content_type = 'LayoutPage' AND content_id = 415024 AND last_n = 3650 LIMIT 1",
        expected_intent=QueryIntent.DATA_RETRIEVAL,
        description="Complex content view query"
    ),

    TestQuery(
        sql="BEGIN",
        expected_intent=QueryIntent.TRANSACTION_CONTROL,
        description="Transaction begin"
    ),

    TestQuery(
        sql="SELECT products.title, COUNT(line_items.id) as item_count FROM products LEFT JOIN line_items ON products.id = line_items.product_id GROUP BY products.id",
        expected_intent=QueryIntent.DATA_RETRIEVAL,  # Complex aggregation
        description="Product popularity report with aggregation"
    )
]


async def test_semantic_analysis():
    """Test the semantic SQL analyzer with diverse queries."""
    print("🧪 Testing Semantic SQL Analysis")
    print("=" * 50)

    analyzer = SemanticSQLAnalyzer()

    for i, test_query in enumerate(TEST_QUERIES, 1):
        print(f"\n{i}. {test_query.description}")
        print(f"SQL: {test_query.sql}")

        try:
            analysis = analyzer.analyze(test_query.sql)

            print(f"✅ Intent: {analysis.intent.value}")
            print(f"✅ Tables: {[t.name for t in analysis.tables]}")
            print(f"✅ Models: {[t.rails_model for t in analysis.tables]}")
            print(f"✅ Complexity: {analysis.complexity}")
            print(f"✅ WHERE conditions: {len(analysis.where_conditions)}")

            # Check if intent matches expectation
            if analysis.intent == test_query.expected_intent:
                print("✅ Intent recognition: CORRECT")
            else:
                print(f"❌ Intent recognition: Expected {test_query.expected_intent.value}, got {analysis.intent.value}")

            # Show Rails patterns
            if analysis.rails_patterns:
                print(f"✅ Rails patterns: {analysis.rails_patterns[:3]}...")  # Show first 3
            else:
                print("⚠️ No Rails patterns inferred")

        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()


async def test_enhanced_search_tool():
    """Test the enhanced search tool with semantic analysis."""
    print("\n\n🔧 Testing Enhanced Search Tool")
    print("=" * 50)

    tool = EnhancedSQLRailsSearch(project_root=".")

    # Test with the original problematic query
    test_sql = 'SELECT 1 AS one FROM "line_items" WHERE "line_items"."cart_id" = $1 LIMIT 1'

    print(f"SQL: {test_sql}")

    try:
        result = await tool.execute({
            "sql": test_sql,
            "include_usage_sites": True,
            "max_results": 5
        })

        print(f"✅ Fingerprint: {result.get('fingerprint')}")
        print(f"✅ Analysis: {result.get('sql_analysis')}")
        print(f"✅ Verification: {result.get('verify')}")
        print(f"✅ Matches found: {len(result.get('matches', []))}")

        # Show first few matches
        for i, match in enumerate(result.get('matches', [])[:3], 1):
            print(f"  {i}. {match['path']}:{match['line']} [{match['confidence']}]")
            print(f"     Why: {', '.join(match['why'])}")

    except Exception as e:
        print(f"❌ Tool execution failed: {e}")
        import traceback
        traceback.print_exc()


def compare_with_old_approach():
    """Compare new semantic approach with old regex-based approach."""
    print("\n\n📊 Comparing Old vs New Approach")
    print("=" * 50)

    test_sql = 'SELECT 1 AS one FROM "line_items" WHERE "line_items"."cart_id" = $1 LIMIT 1'

    # Old approach problems
    print("❌ Old Approach Problems:")
    print("  - Wrong fingerprint: 'SELECT 1 FROM table'")
    print("  - Missed WHERE conditions")
    print("  - No semantic understanding")
    print("  - Hard-coded regex patterns")

    # New approach benefits
    analyzer = SemanticSQLAnalyzer()
    analysis = analyzer.analyze(test_sql)

    print("✅ New Approach Benefits:")
    print(f"  - Correct intent: {analysis.intent.value}")
    print(f"  - Proper table extraction: {[t.name for t in analysis.tables]}")
    print(f"  - WHERE analysis: {len(analysis.where_conditions)} conditions")
    print(f"  - Foreign key detection: {any(c.column.is_foreign_key for c in analysis.where_conditions)}")
    print(f"  - Rails patterns: {len(analysis.rails_patterns)} generated")


async def main():
    """Run all tests."""
    print("🚀 Semantic SQL Detective Test Suite")
    print("=" * 60)

    await test_semantic_analysis()
    await test_enhanced_search_tool()
    compare_with_old_approach()

    print("\n✅ Test suite completed!")


if __name__ == "__main__":
    asyncio.run(main())
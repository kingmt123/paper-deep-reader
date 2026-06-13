# Batch Compilation Template

After all individual paper notes are generated (one per subagent), the main agent compiles them into a consolidated deliverable.

## Compilation Structure

```markdown
# <文件夹名/主题> — 文献速读汇总

> 生成日期: {date} | 方法: paper-deep-reader {mode}模式
> 共{N}篇: {papers}篇论文 + {patents}项专利

---

## 📁 <子文件夹1> ({count}篇)

### {序号}. {论文标题简称}
- **期刊**: {journal} ({year}) | **作者**: {authors_short}
- **一句话**: {one_sentence_summary}
- **核心问题**: {core_problem_2_3_sentences}
- **关键方法**: {key_method_bullets}
- **关键结果**: {key_results_with_numbers}
- **不足**: {limitations_specific}

---

## 📊 横向对比表

| # | 文献 | 年份 | 期刊 | 核心方法 | 关键结果 | 最大问题 |
|---|------|------|------|----------|----------|----------|
| 1 | {short_name} | {year} | {journal} | {method} | {result} | {flaw} |
| 2 | ... | ... | ... | ... | ... | ... |

## 🔑 综合启示

{synthesis_connecting_findings_to_user_research_topic}

## 📋 每个最致命问题

| # | 文献 | 最致命问题 |
|---|------|-----------|
| 1 | {name} | {specific_direct_criticism} |

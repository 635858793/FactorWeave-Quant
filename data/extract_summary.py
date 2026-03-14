file_path = r"D:\DevelopTool\FreeCode\HIkyuu-UI\hikyuu-ui\data\deep_audit_report.txt"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find("七、关键问题汇总")
end = content.find("报告生成时间")

if start > 0 and end > start:
    section = content[start:end]
    print(section)

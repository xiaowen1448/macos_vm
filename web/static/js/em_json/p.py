# 输入文件路径
input_file = "emoji_list_full.txt"
output_file = "emoji_wrapped.txt"

# 每行显示多少个 emoji
per_line = 20

with open(input_file, "r", encoding="utf-8") as f:
    emojis = [line.strip() for line in f if line.strip()]

# 分组拼接
lines = ["".join(emojis[i:i + per_line]) for i in range(0, len(emojis), per_line)]

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"处理完成！已生成 {output_file}")

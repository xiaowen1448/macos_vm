def are_all_unique(arr):
    # 比较原始长度与集合长度
    #判断数组值是否重复
    return len(arr) == len(set(arr))

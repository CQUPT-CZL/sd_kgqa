import graphviz
from typing import List
import io
from PIL import Image

def visualize_paths_with_graphviz(paths: List[str], save_path: str = None) -> Image.Image:
    """
    使用 Graphviz (dot 引擎) 来可视化路径，自动处理布局。

    Args:
        paths: 推理路径列表
        save_path: 可选，保存图片的路径（如 'output.png'）

    Returns:
        PIL Image 对象
    """
    # 1. 创建一个有向图 (Digraph)
    # 'LR' 表示布局从左到右 (Left to Right)
    g = graphviz.Digraph(comment='Knowledge Graph Paths')
    g.attr(rankdir='LR') 

    # 2. 定义统一样式 (使用您原有的配色方案)
    g.attr('node', 
           shape='box', 
           style='rounded,filled', 
           fillcolor='#A7C7E7', 
           color='#2E86AB',
           fontname='Arial Unicode MS') # 确保字体支持中文
    g.attr('edge', 
           color='#E63946', 
           fontcolor='#E63946', 
           fontname='Arial Unicode MS',
           fontsize='9')

    # 3. 解析路径并构建图
    nodes = set()
    edge_labels = {} # 使用 (source, target) -> set(relations) 来合并相同边上的不同关系

    for path in paths:
        parts = path.split('->')
        entities = [parts[i].strip() for i in range(0, len(parts), 2)]
        relations = [parts[i].strip() for i in range(1, len(parts), 2)]

        for entity in entities:
            nodes.add(entity)

        for i in range(len(entities) - 1):
            source = entities[i]
            target = entities[i + 1]
            relation = relations[i] if i < len(relations) else ""
            
            key = (source, target)
            if key not in edge_labels:
                edge_labels[key] = set()
            edge_labels[key].add(relation)

    # 4. 将节点和边添加到 Graphviz 对象
    for node in nodes:
        g.node(node) # Graphviz 自动处理重复添加
        
    for (source, target), relations in edge_labels.items():
        # 合并关系标签
        label = "/".join(r for r in relations if r)
        g.edge(source, target, label=label)

    # 5. 渲染并返回 PIL Image
    if save_path:
        # Graphviz 会自动添加 .png 后缀
        filename = save_path.rsplit('.', 1)[0]
        g.render(filename, format='png', cleanup=True)
        print(f"✓ Graphviz 可视化完成：{filename}.png")

    # 将图像数据读入 PIL Image
    try:
        png_data = g.pipe(format='png')
        img = Image.open(io.BytesIO(png_data))
        return img
    except graphviz.backend.execute.CalledProcessError as e:
        print("="*50)
        print("错误：Graphviz 执行失败。")
        print("请确保您已经安装了 Graphviz 可执行程序，并将其添加到了系统 PATH。")
        print(f"错误详情: {e}")
        print("="*50)
        return None


if __name__ == "__main__":
    # 使用您提供的参考路径
    test_paths_shared = [
        "提升中间辊道送钢速度->解决->输送时间长->导致->带钢头部温降->导致->头部温度过低->导致->轧机瞬时弹跳量增大->导致->精轧机穿带稳定性下降",
        "冷却水与高压水让头控制->解决->直接冷却->导致->带钢头部温降->导致->头部温度过低->导致->轧机瞬时弹跳量增大->导致->精轧机穿带稳定性下降",
        "冷却水与高压水让头控制->解决->直接冷却->导致->带钢头部温降->解决->保温罩中间辊道送钢速度提高",
        "提升中间辊道送钢速度->解决->输送时间长->导致->带钢头部温降->解决->优化飞剪剪刃冷却水开启策略"
    ]
    
    print("测试: 使用 Graphviz 渲染多条共享节点路径")
    img_gv = visualize_paths_with_graphviz(test_paths_shared, save_path="test_shared_graphviz.png")
    
    if img_gv:
        # img_gv.show() # 取消注释以自动打开图片
        print("✓ Graphviz 版本已成功生成。")
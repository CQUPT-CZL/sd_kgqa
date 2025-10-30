import streamlit as st
import plotly.graph_objects as go
import networkx as nx
from typing import List, Dict, Set, Tuple
import numpy as np

def format_node_text(text: str, max_length: int = 8) -> str:
    """
    格式化节点文字，处理长文字
    
    Args:
        text: 原始文字
        max_length: 单行最大长度
    
    Returns:
        格式化后的文字
    """
    if len(text) <= max_length:
        return text
    
    # 如果文字太长，尝试在合适的位置换行
    if len(text) <= max_length * 2:
        # 尝试找到中间的分割点
        mid = len(text) // 2
        # 寻找最近的空格或标点符号
        for i in range(mid - 2, mid + 3):
            if i > 0 and i < len(text) and text[i] in ' ，。、':
                return text[:i] + '<br>' + text[i+1:]
        # 如果没有找到合适的分割点，直接在中间分割
        return text[:mid] + '<br>' + text[mid:]
    else:
        # 文字太长，截断并添加省略号
        return text[:max_length-1] + '...'

def parse_paths_to_networkx(paths: List[str], center_entity: str) -> nx.DiGraph:
    """
    将路径列表解析为NetworkX图
    
    Args:
        paths: 路径字符串列表，格式如 "A->关系->B->关系->C"
        center_entity: 中心实体名称
    
    Returns:
        NetworkX有向图
    """
    G = nx.DiGraph()
    
    for path in paths:
        if not path or '->' not in path:
            continue
            
        # 分割路径，获取实体和关系
        parts = path.split('->')
        
        # 遍历路径中的每个部分
        for i in range(0, len(parts) - 1, 2):  # 每两个元素为一组：实体->关系->实体
            if i + 2 < len(parts):
                source = parts[i].strip()
                relation = parts[i + 1].strip()
                target = parts[i + 2].strip()
                
                # 添加节点属性
                if source not in G:
                    G.add_node(source, is_center=(source == center_entity))
                if target not in G:
                    G.add_node(target, is_center=(target == center_entity))
                
                # 添加边
                G.add_edge(source, target, relation=relation)
    
    return G

def create_plotly_graph(G: nx.DiGraph, center_entity: str):
    """
    使用plotly创建图谱可视化
    
    Args:
        G: NetworkX图
        center_entity: 中心实体名称
    
    Returns:
        plotly图形对象
    """
    # 使用spring布局，调整参数让节点更紧密
    pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)
    
    # 准备边的坐标
    edge_x = []
    edge_y = []
    edge_info = []
    
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        
        # 获取关系信息
        relation = G[edge[0]][edge[1]].get('relation', '')
        edge_info.append(f"{edge[0]} --{relation}--> {edge[1]}")
    
    # 创建边的轨迹
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=2, color='#888'),
        hoverinfo='none',
        mode='lines'
    )
    
    # 准备节点的坐标和信息
    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    node_sizes = []
    node_info = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        # 格式化节点文字，处理长文字
        formatted_text = format_node_text(node, max_length=6)
        node_text.append(formatted_text)
        
        # 判断是否为中心节点
        is_center = G.nodes[node].get('is_center', False)
        
        if is_center:
            node_colors.append('#FF4444')  # 红色表示中心节点
            node_sizes.append(100)  # 增大中心节点
        else:
            node_colors.append('#2E86AB')  # 蓝色表示普通节点
            node_sizes.append(80)  # 增大普通节点
        
        # 节点信息
        adjacencies = list(G.neighbors(node))
        node_info.append(f'{node}<br>连接数: {len(adjacencies)}<br>邻居: {", ".join(adjacencies[:3])}{"..." if len(adjacencies) > 3 else ""}')
    
    # 创建节点的轨迹
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=node_text,
        textposition="middle center",
        textfont=dict(size=12, color="white", family="Arial Black"),
        hovertext=node_info,
        marker=dict(
            showscale=False,
            color=node_colors,
            size=node_sizes,
            line=dict(width=2, color="white")
        )
    )
    
    # 创建图形
    fig = go.Figure(data=[edge_trace, node_trace],
                   layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20,l=5,r=5,t=40),
                        annotations=[ dict(
                            text="红色节点为中心实体，蓝色节点为相关实体",
                            showarrow=False,
                            xref="paper", yref="paper",
                            x=0.005, y=-0.002,
                            xanchor='left', yanchor='bottom',
                            font=dict(color="gray", size=12)
                        )],
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        plot_bgcolor='white'
                    ))
    
    return fig

def display_knowledge_graph_plotly(paths: List[str], center_entity: str):
    """
    在Streamlit中显示基于plotly的知识图谱
    
    Args:
        paths: 路径字符串列表
        center_entity: 中心实体名称
    """
    if not paths:
        st.warning("没有找到相关的路径数据")
        return
    
    # 解析路径为图
    G = parse_paths_to_networkx(paths, center_entity)
    
    if not G.nodes():
        st.warning("无法解析路径数据为图谱")
        return
    
    # 显示统计信息
    st.subheader("🔗 知识图谱可视化")
    st.info(f"中心实体: **{center_entity}** (红色节点)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("节点数量", len(G.nodes()))
    with col2:
        st.metric("边数量", len(G.edges()))
    with col3:
        st.metric("路径数量", len(paths))
    
    # 创建并显示图谱
    fig = create_plotly_graph(G, center_entity)
    st.plotly_chart(fig, use_container_width=True)
    
    # 显示关系详情
    with st.expander("🔍 查看关系详情"):
        for edge in G.edges(data=True):
            source, target, data = edge
            relation = data.get('relation', '未知关系')
            st.write(f"**{source}** --{relation}--> **{target}**")
    
    # 显示原始路径（可折叠）
    with st.expander("📋 查看原始路径"):
        for i, path in enumerate(paths, 1):
            st.write(f"{i}. {path}")
    
    return G
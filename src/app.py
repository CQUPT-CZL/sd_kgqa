import streamlit as st
from pipeline import step1_entity_recognition, step2_get_subgraph, step3_qa_with_llm
from graph_visualizer_plotly import display_knowledge_graph_plotly

st.title("KG QA")

query = st.text_input("Enter your query:")

if st.button("Ask"):
    if query:
        with st.spinner("Step 1: Recognizing entities..."):
            entity = step1_entity_recognition(query)
        
        if entity:
            st.success(f"Entity found: {entity}")
            
            with st.spinner("Step 2: Retrieving subgraph..."):
                entity_path = step2_get_subgraph(entity)
            st.info("Subgraph retrieved.")
            if entity_path:
                # 显示知识图谱可视化
                display_knowledge_graph_plotly(entity_path, entity)

            with st.spinner("Step 3: Answering question..."):
                result = step3_qa_with_llm(query, entity_path)
            st.info("Question answered.")
            st.write(result)
        else:
            st.error("No entity found in the query.")
    else:
        st.warning("Please enter a query.")
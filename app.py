import streamlit as st

from src.database import initialize_database, load_products, save_product


initialize_database()

st.set_page_config(
    page_title="Product Manager Central",
    page_icon="📊",
    layout="wide",
)

st.title("Product Manager Central")
st.subheader("AI-assisted Product Management Workspace")

product_name = st.text_input("Product Name")

product_idea = st.text_area("Describe your product idea")

target_user = st.text_input("Target User")

business_goal = st.text_area("Business Goal")

if st.button("Create Product Foundation"):
    if not product_name.strip():
        st.error("Please enter a product name.")
    elif not product_idea.strip():
        st.error("Please describe your product idea.")
    elif not target_user.strip():
        st.error("Please enter the target user.")
    elif not business_goal.strip():
        st.error("Please enter the business goal.")
    else:
        save_product(
            product_name,
            product_idea,
            target_user,
            business_goal,
        )
        st.success("Product foundation saved successfully!")

st.divider()
st.subheader("Saved Products")

saved_products = load_products()

if saved_products.empty:
    st.info("No products have been saved yet.")
else:
    st.dataframe(
        saved_products,
        use_container_width=True,
        hide_index=True,
    )
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import zipfile
from io import BytesIO

# Add progress tracking
def main():
    st.title("Virtual Meter Data Generator App")
    
    # Sidebar for additional info
    with st.sidebar:
        st.header("About")
        st.info("This app generates synthetic meter data for testing purposes.")
        st.header("File Requirements")
        st.markdown("""
        - Excel file with single column
        - No header row
        - One meter ID per row
        - Maximum 1000 meters recommended
        """)
    
    st.markdown("""
    **Instructions:**
    - Upload an Excel file with a single column of Virtual Meters (no header)
    - Click 'Generate Data' to process
    - The app will generate a table and split it into 30 Excel files in a ZIP
    """)

    # File uploader with size limit
    uploaded_file = st.file_uploader("Upload Excel file", 
                                   type=['xlsx'],
                                   help="Upload an Excel file with meter IDs in a single column")
    
    if uploaded_file:
        # Show file info
        file_details = {"Filename": uploaded_file.name, 
                       "File size": f"{uploaded_file.size / 1024:.2f} KB"}
        st.write(file_details)
        
        # Preview uploaded data
        try:
            df_preview = pd.read_excel(uploaded_file, header=None)
            st.subheader("Preview of Uploaded Meters")
            st.dataframe(df_preview.head(10), use_container_width=True)
            st.write(f"Total meters found: {len(df_preview)}")
        except Exception as e:
            st.error(f"Could not read uploaded file: {str(e)}")
            return
        
        generate_button = st.button("Generate Data", type="primary")
        
        if generate_button:
            # Reset uploaded file to beginning
            uploaded_file.seek(0)
            
            with st.spinner("Generating virtual meter data... This may take a moment."):
                try:
                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.text("Reading uploaded file...")
                    df = pd.read_excel(uploaded_file, header=None)
                    progress_bar.progress(10)
                    
                    # Validate upload
                    status_text.text("Validating data...")
                    meters = validate_uploaded_file(df)
                    progress_bar.progress(20)
                    
                    # Generate timestamps
                    status_text.text("Generating timestamps...")
                    timestamps = generate_timestamps()
                    progress_bar.progress(30)
                    
                    # Create full DataFrame
                    status_text.text("Creating dataset...")
                    full_df = create_full_df(meters, timestamps)
                    progress_bar.progress(50)
                    
                    # Validate DataFrame
                    status_text.text("Validating dataset...")
                    validate_df(full_df, meters, timestamps)
                    progress_bar.progress(60)
                    
                    # Show dataset info
                    st.subheader("Generated Dataset Info")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Meters", len(meters))
                    with col2:
                        st.metric("Total Timestamps", len(timestamps))
                    with col3:
                        st.metric("Total Records", len(full_df))
                    
                    # Preview generated data
                    with st.expander("Preview Generated Data"):
                        st.dataframe(full_df.head(1000), use_container_width=True)
                    
                    # Split into chunks
                    status_text.text("Splitting data into files...")
                    chunks = np.array_split(full_df, 30)
                    progress_bar.progress(80)
                    
                    # Create ZIP
                    status_text.text("Creating ZIP file...")
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for i, chunk in enumerate(chunks, 1):
                            excel_buffer = BytesIO()
                            chunk.to_excel(excel_buffer, index=False, engine='openpyxl')
                            excel_buffer.seek(0)
                            zip_file.writestr(f"virtual_meters_part_{i:02d}.xlsx", 
                                            excel_buffer.getvalue())
                    
                    progress_bar.progress(100)
                    status_text.text("Complete!")
                    
                    st.success("✅ Generation complete! Download the ZIP file below.")
                    
                    # Download button
                    st.download_button(
                        label="📥 Download ZIP File",
                        data=zip_buffer.getvalue(),
                        file_name=f"virtual_meters_data_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                        mime="application/zip",
                        help="Click to download the generated data as a ZIP file containing 30 Excel files"
                    )
                    
                    # Show file contents
                    with st.expander("ZIP File Contents"):
                        st.write("The ZIP file contains the following Excel files:")
                        for i in range(1, 31):
                            st.write(f"- `virtual_meters_part_{i:02d}.xlsx`")
                
                except ValueError as ve:
                    st.error(f"❌ Validation Error: {str(ve)}")
                except Exception as e:
                    st.error(f"❌ An unexpected error occurred: {str(e)}")
                    st.info("💡 Please check your file format and try again.")

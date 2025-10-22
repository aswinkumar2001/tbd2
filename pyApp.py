import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import zipfile
from io import BytesIO
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to generate timestamps with configurable parameters
def generate_timestamps(start_date, end_date, frequency):
    timestamps = pd.date_range(start=start_date, end=end_date, freq=frequency)
    return timestamps

# Enhanced validation function that handles errors gracefully
def validate_uploaded_file(df):
    validation_issues = []
    valid_meters = []
    invalid_meters = []
    
    if df.empty:
        raise ValueError("Uploaded Excel is empty.")
    
    # Skip first row (header) and process from second row onwards
    meter_data = df.iloc[1:, 0] if len(df) > 1 else pd.Series(dtype=object)
    
    if len(meter_data) == 0:
        raise ValueError("No meter data found after skipping header row.")
    
    for idx, meter in meter_data.dropna().items():
        original_idx = idx + 2  # +2 because we skip header and pandas is 0-indexed
        try:
            # Basic validation - meter should not be empty and should be convertible to string
            if pd.isna(meter) or str(meter).strip() == '':
                invalid_meters.append((original_idx, meter, "Empty or NaN value"))
                continue
                
            meter_str = str(meter).strip()
            if len(meter_str) == 0:
                invalid_meters.append((original_idx, meter, "Empty string after stripping"))
                continue
                
            valid_meters.append(meter_str)
            
        except Exception as e:
            invalid_meters.append((original_idx, meter, f"Validation error: {str(e)}"))
    
    # Check for duplicates among valid meters
    unique_meters = []
    duplicate_meters = []
    seen_meters = set()
    
    for meter in valid_meters:
        if meter in seen_meters:
            duplicate_meters.append(meter)
        else:
            unique_meters.append(meter)
            seen_meters.add(meter)
    
    if duplicate_meters:
        validation_issues.append(f"Found {len(duplicate_meters)} duplicate meters (will be deduplicated)")
    
    if invalid_meters:
        validation_issues.append(f"Found {len(invalid_meters)} invalid meter entries")
    
    return unique_meters, invalid_meters, duplicate_meters, validation_issues

# Optimized function to create the full DataFrame
def create_full_df(meters, timestamps):
    """More memory-efficient creation of large DataFrames"""
    if not meters or not len(timestamps):
        raise ValueError("No meters or timestamps to process")
    
    # Create arrays and then convert to DataFrame (more memory efficient)
    meter_array = np.repeat(meters, len(timestamps))
    timestamp_array = np.tile(timestamps, len(meters))
    
    full_df = pd.DataFrame({
        'Asset name': meter_array,
        'Timestamp': timestamp_array
    })
    full_df['KPI Trigger'] = 1
    
    # Format timestamps
    full_df['Timestamp'] = full_df['Timestamp'].dt.strftime('%d/%m/%Y %H:%M')
    
    return full_df.sort_values(['Asset name', 'Timestamp']).reset_index(drop=True)

# Enhanced validation for generated DataFrame
def validate_generated_df(full_df, meters, timestamps):
    validation_errors = []
    warnings = []
    
    # Check if all meters are present
    unique_meters_in_df = full_df['Asset name'].unique()
    if len(unique_meters_in_df) != len(meters):
        missing_meters = set(meters) - set(unique_meters_in_df)
        if missing_meters:
            validation_errors.append(f"Missing meters in generated data: {list(missing_meters)[:5]}")
    
    # Check for duplicates
    duplicates = full_df.duplicated(subset=['Asset name', 'Timestamp']).sum()
    if duplicates > 0:
        validation_errors.append(f"Found {duplicates} duplicated entries")
    
    # Check KPI Trigger values
    invalid_kpi = full_df[full_df['KPI Trigger'] != 1]
    if len(invalid_kpi) > 0:
        validation_errors.append(f"Found {len(invalid_kpi)} records with KPI Trigger != 1")
    
    # Sample check timestamps for a few meters
    sample_meters = meters[:min(3, len(meters))]  # Check first 3 meters
    for meter in sample_meters:
        meter_data = full_df[full_df['Asset name'] == meter]
        if len(meter_data) != len(timestamps):
            warnings.append(f"Meter {meter} has {len(meter_data)} records, expected {len(timestamps)}")
    
    return validation_errors, warnings

# Function to split DataFrame into chunks
def split_dataframe(df, num_chunks):
    """Split DataFrame into approximately equal chunks"""
    if num_chunks <= 1:
        return [df]
    
    chunk_size = len(df) // num_chunks
    chunks = []
    
    for i in range(num_chunks):
        start_idx = i * chunk_size
        if i == num_chunks - 1:  # Last chunk gets all remaining rows
            end_idx = len(df)
        else:
            end_idx = (i + 1) * chunk_size
        chunks.append(df.iloc[start_idx:end_idx].copy())
    
    return chunks

def main():
    st.set_page_config(page_title="Virtual Meter Data Generator", layout="wide")
    st.title("📊 Virtual Meter Data Generator App")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Date range selection
        start_date = st.date_input(
            "Start Date", 
            datetime(2024, 1, 1),
            help="Start date for data generation"
        )
        end_date = st.date_input(
            "End Date", 
            datetime(2025, 8, 31),
            help="End date for data generation"
        )
        
        # Frequency selection
        frequency = st.selectbox(
            "Data Frequency",
            ["30T", "1H", "15T"],
            index=0,
            help="Time interval between data points"
        )
        
        # Number of output files
        num_files = st.slider("Number of output files", 1, 50, 30)
        
        st.header("ℹ️ About")
        st.info("This app generates synthetic meter data for testing purposes.")
        
        st.header("📋 File Requirements")
        st.markdown("""
        - Excel file with single column
        - First row is treated as header (will be skipped)
        - One meter ID per row after header
        - Maximum 5000 meters recommended
        - Supported formats: .xlsx, .xls
        """)

    # Main content area
    st.markdown("""
    **Instructions:**
    1. Upload an Excel file with a single column of Virtual Meters (first row is header)
    2. Configure the parameters in the sidebar
    3. Click 'Generate Data' to process
    4. Download the generated ZIP file containing multiple Excel files
    """)

    # File uploader
    uploaded_file = st.file_uploader(
        "Upload Excel file", 
        type=['xlsx', 'xls'],
        help="Upload an Excel file with meter IDs in a single column (first row = header)"
    )
    
    if uploaded_file:
        try:
            # Preview uploaded data
            df_preview = pd.read_excel(uploaded_file, header=None)
            
            st.subheader("📄 Preview of Uploaded File")
            st.write(f"File: {uploaded_file.name} | Size: {uploaded_file.size / 1024:.2f} KB")
            
            # Show preview with highlighting for header row
            preview_df = df_preview.head(10).copy()
            st.dataframe(preview_df, use_container_width=True)
            
            # Show header info
            if len(df_preview) > 0:
                st.info(f"**Header row (will be skipped):** '{df_preview.iloc[0, 0]}'")
                st.write(f"**Total rows (including header):** {len(df_preview)}")
        
        except Exception as e:
            st.error(f"❌ Could not read uploaded file: {str(e)}")
            return

        generate_button = st.button("🚀 Generate Data", type="primary", use_container_width=True)
        
        if generate_button:
            # Reset uploaded file to beginning
            uploaded_file.seek(0)
            
            with st.spinner("Generating virtual meter data... This may take a moment for large datasets."):
                try:
                    # Initialize progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    log_container = st.container()
                    
                    with log_container:
                        st.subheader("🔍 Processing Log")
                    
                    # Step 1: Read uploaded file
                    status_text.text("Step 1/6: Reading uploaded file...")
                    df = pd.read_excel(uploaded_file, header=None)
                    progress_bar.progress(10)
                    
                    with log_container:
                        st.write("✅ File read successfully")
                        st.write(f"📊 Raw data shape: {df.shape}")
                    
                    # Step 2: Validate upload with error tolerance
                    status_text.text("Step 2/6: Validating meter data...")
                    try:
                        meters, invalid_meters, duplicate_meters, validation_issues = validate_uploaded_file(df)
                        progress_bar.progress(25)
                        
                        with log_container:
                            st.write("✅ Validation completed")
                            st.write(f"📋 Valid meters found: {len(meters)}")
                            
                            # Show validation issues as warnings
                            for issue in validation_issues:
                                st.warning(issue)
                            
                            # Show invalid meters if any
                            if invalid_meters:
                                st.error(f"❌ Found {len(invalid_meters)} invalid meter entries:")
                                with st.expander("View invalid meters"):
                                    for row_num, meter_value, reason in invalid_meters[:20]:  # Show first 20
                                        st.write(f"Row {row_num}: '{meter_value}' - {reason}")
                                    if len(invalid_meters) > 20:
                                        st.write(f"... and {len(invalid_meters) - 20} more")
                            
                            # Show duplicate meters if any
                            if duplicate_meters:
                                st.warning(f"⚠️ Found {len(duplicate_meters)} duplicate meters (automatically deduplicated):")
                                with st.expander("View duplicate meters"):
                                    for meter in duplicate_meters[:10]:  # Show first 10
                                        st.write(f"'{meter}'")
                                    if len(duplicate_meters) > 10:
                                        st.write(f"... and {len(duplicate_meters) - 10} more")
                    
                    except ValueError as ve:
                        st.error(f"❌ Critical validation error: {str(ve)}")
                        return
                    
                    # Check if we have any valid meters to process
                    if not meters:
                        st.error("❌ No valid meters found to process. Please check your input file.")
                        return
                    
                    # Step 3: Generate timestamps
                    status_text.text("Step 3/6: Generating timestamps...")
                    try:
                        timestamps = generate_timestamps(
                            datetime.combine(start_date, datetime.min.time()),
                            datetime.combine(end_date, datetime.min.time()),
                            frequency
                        )
                        progress_bar.progress(40)
                        
                        with log_container:
                            st.write(f"✅ Timestamps generated: {len(timestamps)} intervals")
                            st.write(f"📅 Date range: {start_date} to {end_date}")
                            st.write(f"⏱️ Frequency: {frequency}")
                    
                    except Exception as e:
                        st.error(f"❌ Error generating timestamps: {str(e)}")
                        return
                    
                    # Step 4: Create full DataFrame
                    status_text.text("Step 4/6: Creating dataset...")
                    try:
                        full_df = create_full_df(meters, timestamps)
                        progress_bar.progress(60)
                        
                        with log_container:
                            st.write(f"✅ Dataset created: {len(full_df):,} total records")
                            st.write(f"💾 Memory usage: {full_df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
                    
                    except Exception as e:
                        st.error(f"❌ Error creating dataset: {str(e)}")
                        return
                    
                    # Step 5: Validate generated DataFrame
                    status_text.text("Step 5/6: Validating generated data...")
                    validation_errors, validation_warnings = validate_generated_df(full_df, meters, timestamps)
                    progress_bar.progress(75)
                    
                    with log_container:
                        if validation_errors:
                            for error in validation_errors:
                                st.error(f"❌ {error}")
                        else:
                            st.write("✅ Data validation passed")
                        
                        if validation_warnings:
                            for warning in validation_warnings:
                                st.warning(f"⚠️ {warning}")
                    
                    # Step 6: Split data and create ZIP
                    status_text.text("Step 6/6: Creating output files...")
                    try:
                        chunks = split_dataframe(full_df, num_files)
                        
                        zip_buffer = BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            for i, chunk in enumerate(chunks, 1):
                                excel_buffer = BytesIO()
                                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                                    chunk.to_excel(writer, index=False, sheet_name='MeterData')
                                excel_buffer.seek(0)
                                zip_file.writestr(f"virtual_meters_part_{i:02d}.xlsx", excel_buffer.getvalue())
                        
                        progress_bar.progress(100)
                        status_text.text("🎉 Complete!")
                        
                        with log_container:
                            st.write(f"✅ ZIP file created with {len(chunks)} parts")
                            for i, chunk in enumerate(chunks, 1):
                                st.write(f"📁 Part {i:02d}: {len(chunk):,} records")
                    
                    except Exception as e:
                        st.error(f"❌ Error creating ZIP file: {str(e)}")
                        return
                    
                    # Display final results
                    st.success("✅ Generation complete! Download the ZIP file below.")
                    
                    # Show dataset summary
                    st.subheader("📈 Dataset Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Valid Meters", len(meters))
                    with col2:
                        st.metric("Time Intervals", len(timestamps))
                    with col3:
                        st.metric("Total Records", f"{len(full_df):,}")
                    with col4:
                        total_size = len(full_df) * 100 / (1024 * 1024)  # Approximate size
                        st.metric("Approx. Size", f"{total_size:.1f} MB")
                    
                    # Preview generated data
                    with st.expander("🔍 Preview Generated Data (First 1000 records)"):
                        st.dataframe(full_df.head(1000), use_container_width=True)
                    
                    # Download button
                    timestamp_str = datetime.now().strftime('%Y%m%d_%H%M')
                    st.download_button(
                        label="📥 Download ZIP File",
                        data=zip_buffer.getvalue(),
                        file_name=f"virtual_meters_data_{timestamp_str}.zip",
                        mime="application/zip",
                        help="Click to download the generated data as a ZIP file",
                        use_container_width=True
                    )
                    
                    # Show file contents
                    with st.expander("📂 ZIP File Contents"):
                        st.write("The ZIP file contains the following Excel files:")
                        for i in range(1, len(chunks) + 1):
                            st.write(f"- `virtual_meters_part_{i:02d}.xlsx`")
                
                except Exception as e:
                    st.error(f"❌ An unexpected error occurred: {str(e)}")
                    st.info("💡 Please check your file format and try again.")
                    logger.exception("Unexpected error in main process")
    
    else:
        st.info("👆 Please upload an Excel file to get started.")

if __name__ == "__main__":
    main()

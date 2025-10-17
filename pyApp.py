# Add configuration in sidebar
with st.sidebar:
    st.header("Configuration")
    
    # Date range selection
    start_date = st.date_input("Start date", datetime(2024, 1, 1))
    end_date = st.date_input("End date", datetime(2025, 8, 31))
    
    # Frequency selection
    frequency = st.selectbox(
        "Data frequency",
        ["30T", "1H", "15T"],
        help="Time interval between data points"
    )
    
    # Number of output files
    num_files = st.slider("Number of output files", 1, 50, 30)

# Update generate_timestamps function to use config
def generate_timestamps(start_date, end_date, frequency):
    start = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.max.time())
    timestamps = pd.date_range(start=start, end=end, freq=frequency)
    return timestamps
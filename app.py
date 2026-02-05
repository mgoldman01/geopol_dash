"""
Geopolitical Intelligence Dashboard - Main Streamlit Application

Run with: streamlit run app.py

This dashboard provides:
- Event Browser: Search and filter geopolitical events
- Source Status: Monitor data source connectivity and sync status
"""

import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(
    page_title="GeoPol Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

from datetime import date, timedelta

from src.config import get_config, setup_logging
from src.db.database import Database
from src.models.event import EventFilter

# Initialize logging
setup_logging()

# Initialize config
config = get_config()


def get_database() -> Database:
    """Get database connection (cached in session state)."""
    if "db" not in st.session_state:
        db = Database(config.database.path)
        db.connect()
        st.session_state.db = db
    return st.session_state.db


def main():
    """Main application entry point."""
    st.title("Geopolitical Intelligence Dashboard")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Page",
        ["Event Browser", "Source Status", "About"]
    )

    if page == "Event Browser":
        show_event_browser()
    elif page == "Source Status":
        show_source_status()
    else:
        show_about()


def show_event_browser():
    """
    Event Browser page.

    Allows users to search and filter geopolitical events
    with date range, actor, event type, and region filters.
    """
    st.header("Event Browser")
    st.markdown("Search and filter geopolitical events from multiple data sources.")

    db = get_database()

    # Filter controls in columns
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Date Range")
        default_start = date.today() - timedelta(days=config.dashboard.default_date_range_days)
        start_date = st.date_input("Start Date", value=default_start)
        end_date = st.date_input("End Date", value=date.today())

    with col2:
        st.subheader("Filters")

        # Region filter
        region_options = ["All Regions"] + list(config.regions.keys())
        selected_region = st.selectbox("Region", region_options)

        # Get available actors from database
        available_actors = db.get_distinct_actors()
        selected_actors = st.multiselect(
            "Actors (optional)",
            options=available_actors,
            help="Filter to events involving these actors"
        )

    with col3:
        st.subheader("Event Type")

        # Get available event types
        available_types = db.get_distinct_event_types()
        if not available_types:
            available_types = [
                "public_statement", "appeal", "diplomatic_cooperation",
                "material_cooperation", "provide_aid", "protest",
                "threaten", "reduce_relations", "assault", "fight"
            ]

        selected_types = st.multiselect(
            "Event Types (optional)",
            options=available_types,
            help="Filter to specific event categories"
        )

        # Goldstein score range
        st.markdown("**Goldstein Score Range**")
        goldstein_range = st.slider(
            "Score (-10=conflict, +10=cooperation)",
            min_value=-10.0,
            max_value=10.0,
            value=(-10.0, 10.0),
            step=0.5
        )

    # Build filter
    countries = None
    if selected_region and selected_region != "All Regions":
        countries = config.get_region_countries(selected_region)

    event_filter = EventFilter(
        start_date=start_date,
        end_date=end_date,
        actors=selected_actors if selected_actors else None,
        event_types=selected_types if selected_types else None,
        countries=countries,
        min_goldstein=goldstein_range[0],
        max_goldstein=goldstein_range[1],
        limit=config.dashboard.max_display_events
    )

    # Fetch events
    with st.spinner("Fetching events..."):
        events = db.query_events(event_filter)

    # Display results
    st.markdown("---")
    st.subheader(f"Results ({len(events)} events)")

    if not events:
        st.info("No events found matching your criteria. Try adjusting the filters or syncing data from sources.")
    else:
        # Create display table
        display_data = []
        for event in events:
            display_data.append({
                "Date": event.event_date.strftime("%Y-%m-%d"),
                "Actors": ", ".join(event.actors) if event.actors else "-",
                "Type": event.event_type,
                "Location": event.location_country or "-",
                "Goldstein": f"{event.goldstein_score:.1f}" if event.goldstein_score else "-",
                "Headline": (event.headline[:80] + "...") if event.headline and len(event.headline) > 80 else (event.headline or "-"),
                "Source": event.source,
                "URL": event.source_url or ""
            })

        # Display as dataframe with clickable links
        st.dataframe(
            display_data,
            use_container_width=True,
            column_config={
                "URL": st.column_config.LinkColumn("Source Link", display_text="View")
            },
            hide_index=True
        )

        # Event details expander
        st.markdown("### Event Details")
        st.markdown("Click on an event below to see full details:")

        for i, event in enumerate(events[:20]):  # Limit to first 20 for performance
            with st.expander(f"{event.event_date} | {', '.join(event.actors[:2]) if event.actors else 'Unknown'} | {event.event_type}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"**Event ID:** `{event.event_id}`")
                    st.markdown(f"**Source:** {event.source.upper()}")
                    st.markdown(f"**Date:** {event.event_date}")
                    st.markdown(f"**Event Type:** {event.event_type}")
                    st.markdown(f"**CAMEO Code:** {event.cameo_code or 'N/A'}")

                with col2:
                    st.markdown(f"**Actors:** {', '.join(event.actors) if event.actors else 'N/A'}")
                    st.markdown(f"**Location:** {event.location_country or 'N/A'}")
                    st.markdown(f"**Goldstein Score:** {event.goldstein_score or 'N/A'}")
                    st.markdown(f"**Tone:** {event.tone or 'N/A'}")

                if event.headline:
                    st.markdown(f"**Headline:** {event.headline}")

                if event.excerpt:
                    st.markdown(f"**Excerpt:** {event.excerpt}")

                if event.source_url:
                    st.markdown(f"[View Original Source]({event.source_url})")

                if event.metadata:
                    with st.expander("Raw Metadata"):
                        st.json(event.metadata)


def show_source_status():
    """
    Source Status page.

    Shows which data adapters are active, their last sync time,
    and connection status.
    """
    st.header("Source Status")
    st.markdown("Monitor data source connectivity and synchronization status.")

    db = get_database()

    # Get sync status for all sources
    sync_statuses = db.get_all_sync_status()
    status_by_source = {s["source"]: s for s in sync_statuses}

    # Define all sources with their metadata
    from src.adapters.gdelt import GDELTAdapter
    from src.adapters.acled import ACLEDAdapter
    from src.adapters.sipri import SIPRIAdapter
    from src.adapters.news_scraper import NewsScraperAdapter

    sources = [
        ("gdelt", GDELTAdapter()),
        ("acled", ACLEDAdapter()),
        ("sipri", SIPRIAdapter()),
        ("news", NewsScraperAdapter()),
    ]

    # Display each source
    for source_key, adapter in sources:
        metadata = adapter.get_source_metadata()
        sync_status = status_by_source.get(source_key, {})
        is_enabled = config.is_source_enabled(source_key)

        with st.container():
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                st.markdown(f"### {metadata.name}")
                st.caption(metadata.description[:150] + "..." if len(metadata.description) > 150 else metadata.description)

            with col2:
                if is_enabled:
                    st.success("Enabled")
                else:
                    st.warning("Disabled")

            with col3:
                status = sync_status.get("status", "never synced")
                if status == "syncing":
                    st.info("Syncing...")
                elif status == "error":
                    st.error("Error")
                elif status == "idle" and sync_status.get("last_sync_time"):
                    st.success("OK")
                else:
                    st.warning("Not synced")

            with col4:
                # Test connection button
                if st.button(f"Test", key=f"test_{source_key}"):
                    with st.spinner("Testing connection..."):
                        try:
                            connected = adapter.validate_connection()
                            if connected:
                                st.success("Connected")
                            else:
                                st.error("Failed")
                        except NotImplementedError:
                            st.warning("Not implemented")
                        except Exception as e:
                            st.error(f"Error: {str(e)[:50]}")

            # Details expander
            with st.expander("Details"):
                st.markdown(f"**Update Frequency:** {metadata.update_frequency}")
                st.markdown(f"**Coverage Start:** {metadata.coverage_start or 'N/A'}")
                st.markdown(f"**Geographic Coverage:** {metadata.geographic_coverage}")
                st.markdown(f"**Requires API Key:** {'Yes' if metadata.requires_api_key else 'No'}")

                if metadata.documentation_url:
                    st.markdown(f"[Documentation]({metadata.documentation_url})")

                if sync_status:
                    st.markdown("---")
                    st.markdown("**Sync History:**")
                    st.markdown(f"- Last Sync: {sync_status.get('last_sync_time', 'Never')}")
                    st.markdown(f"- Events Synced: {sync_status.get('last_sync_count', 0)}")
                    if sync_status.get("last_error"):
                        st.error(f"Last Error: {sync_status['last_error']}")

            st.markdown("---")

    # Sync controls
    st.subheader("Sync Controls")
    st.markdown("Fetch new events from enabled data sources.")

    col1, col2 = st.columns(2)

    with col1:
        sync_region = st.selectbox(
            "Region to sync",
            options=list(config.regions.keys()),
            index=list(config.regions.keys()).index(config.dashboard.default_region) if config.dashboard.default_region in config.regions else 0
        )

    with col2:
        sync_days = st.number_input(
            "Days to fetch",
            min_value=1,
            max_value=30,
            value=7
        )

    if st.button("Sync GDELT Data", type="primary"):
        sync_gdelt_data(sync_region, sync_days)

    # Database stats
    st.subheader("Database Statistics")
    event_count = db.get_event_count()
    st.metric("Total Events", f"{event_count:,}")


def sync_gdelt_data(region: str, days: int):
    """
    Sync GDELT data for the specified region and time period.

    Args:
        region: Region key from config
        days: Number of days back to fetch
    """
    from src.adapters.gdelt import GDELTAdapter

    db = get_database()
    adapter = GDELTAdapter()

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        db.update_sync_status("gdelt", "syncing")

        status_text.text(f"Fetching GDELT events for {region} from {start_date} to {end_date}...")

        events = adapter.fetch_events(
            date_range=(start_date, end_date),
            region=region
        )

        progress_bar.progress(50)
        status_text.text(f"Fetched {len(events)} events. Inserting into database...")

        inserted = db.insert_events_batch(events)

        progress_bar.progress(100)
        status_text.text(f"Sync complete! Inserted {inserted} new events.")

        db.update_sync_status("gdelt", "idle", event_count=inserted)
        st.success(f"Successfully synced {inserted} new events from GDELT")

    except Exception as e:
        db.update_sync_status("gdelt", "error", error=str(e))
        st.error(f"Sync failed: {str(e)}")
        raise

    finally:
        adapter.close()


def show_about():
    """About page with project information."""
    st.header("About")

    st.markdown("""
    ## Geopolitical Intelligence Dashboard

    A web-based platform for analyzing geopolitical events from multiple data sources.

    ### Core Principles

    - **Transparency First**: All code is inspectable and debuggable
    - **Modular Architecture**: Each component can be tested and replaced independently
    - **Verifiable Claims**: Every analytical statement cites specific source events
    - **Established Methods**: Uses proven event coding frameworks (CAMEO, Goldstein scores)

    ### Data Sources

    | Source | Description | Status |
    |--------|-------------|--------|
    | GDELT | Global event database, 15-minute updates | Active |
    | ACLED | Armed conflict data (requires API key) | Planned |
    | SIPRI | Arms transfers and military spending | Planned |
    | News | Custom news extraction via LLM | Planned |

    ### Event Coding

    Events are coded using the **CAMEO** (Conflict and Mediation Event Observations)
    framework, which provides standardized event types across all data sources.

    The **Goldstein Scale** (-10 to +10) measures conflict-cooperation intensity:
    - **+10**: Maximum cooperation (e.g., military alliance formed)
    - **0**: Neutral events
    - **-10**: Maximum conflict (e.g., war declared)

    ### References

    - [GDELT Project](https://www.gdeltproject.org/)
    - [CAMEO Codebook](https://parusanalytics.com/eventdata/cameo.dir/CAMEO.09b6.pdf)
    - Goldstein, J.S. (1992). "A Conflict-Cooperation Scale for WEIS Events Data"

    ---

    *Built for geopolitical research and analysis*
    """)


if __name__ == "__main__":
    main()

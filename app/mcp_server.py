import os
from mcp.server.fastmcp import FastMCP

# Create the FastMCP server
mcp = FastMCP("travel-buddy-mcp")

@mcp.tool()
def search_flights(destination: str, date: str) -> str:
    """Search for flights to a destination on a specific date.

    Args:
        destination: The destination city or airport code.
        date: The date of travel in YYYY-MM-DD format.
    """
    # Simple simulated flight listings
    return (
        f"Simulated Flight Listings for {destination} on {date}:\n"
        f"1. Skylink SL-102 | Departs: 08:30 AM | Price: $290 | Duration: 2h 45m | Direct\n"
        f"2. AirTransit AT-405 | Departs: 12:15 PM | Price: $340 | Duration: 3h 10m | Direct\n"
        f"3. CloudFlyer CF-808 | Departs: 06:45 PM | Price: $210 | Duration: 4h 20m | 1-stop"
    )

@mcp.tool()
def search_hotels(destination: str, checkin: str, checkout: str) -> str:
    """Search for hotels in a destination for the given check-in/out dates.

    Args:
        destination: The city or area to search.
        checkin: The check-in date in YYYY-MM-DD format.
        checkout: The check-out date in YYYY-MM-DD format.
    """
    # Simple simulated hotel listings
    return (
        f"Simulated Hotel Listings for {destination} ({checkin} to {checkout}):\n"
        f"1. The Grand Plaza Resort | Rating: 4.6* | Price: $180/night | Location: Downtown | Free Breakfast\n"
        f"2. Metro Stay Inn | Rating: 4.1* | Price: $110/night | Location: Near Airport | Gym Access\n"
        f"3. Cozy Corner Boutique Hotel | Rating: 4.8* | Price: $240/night | Location: Historic Center | Spa"
    )

@mcp.tool()
def get_itinerary_ideas(destination: str, interests: str) -> str:
    """Get sightseeing and activity ideas for a destination based on interests.

    Args:
        destination: The city or area.
        interests: Comma-separated list of interests (e.g. food, history, nature).
    """
    # Simple simulated local recommendations
    return (
        f"Simulated Itinerary Ideas for {destination} (Interests: {interests}):\n"
        f"- Morning: Guided walking tour of the historical center, exploring landmarks.\n"
        f"- Afternoon: Visit local museum/market, culinary food tasting experience.\n"
        f"- Evening: Sunset viewpoint walk followed by dining at a top-rated local bistro."
    )

if __name__ == "__main__":
    mcp.run()

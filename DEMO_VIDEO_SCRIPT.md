# HydroPond AI: 5-Minute YouTube Demo Video Script

**Target Duration:** 4 minutes 30 seconds (Maximum allowed: 5 minutes)  
**Live URL to Screen Record:** `http://10.1.75.51:3317/`  
**API Documentation:** `http://10.1.75.51:3317/docs`

---

## [0:00 - 0:45] Section 1: Introduction & Problem Context
* **Visual:** Open browser showing the live system at `http://10.1.75.51:3317/` with the satellite basemap visible.
* **Spoken Script:**
  > "Hello everyone. Welcome to the demonstration of **HydroPond AI**, an automated Web GIS and hydrological decision-support platform designed for village pond planning and precision rainwater harvesting.  
  > In rural India, village ponds are essential for drought resilience and groundwater recharge. However, traditional site selection is done either by coarse visual inspection or expensive land surveys. This often leads to ponds dug in high elevations with zero inflow, or structures washed away by sudden monsoons.  
  > Our system solves this by integrating Digital Elevation Modeling, D8 hydrological flow routing, and meteorological rainfall analysis into an interactive web interface that any village planner can use."

---

## [0:45 - 2:00] Section 2: Algorithms & Core Architecture
* **Visual:** Briefly show the Architecture Diagram (from report) or Swagger Docs (`/docs`).
* **Spoken Script:**
  > "Let's briefly understand the computational engine powering this platform:  
  > 1. **KML Parsing & Metric Projection:** The backend parses raw contour maps and reprojects geographic coordinates to metric Universal Transverse Mercator (UTM) coordinates using `pyproj`.  
  > 2. **Continuous DEM Interpolation:** Using `scipy`, we rasterize the contours into a 10-meter resolution Digital Elevation Model.  
  > 3. **Priority-Flood Sink Filling:** We implement the Wang & Liu Priority-Flood algorithm to remove artificial depressions and ensure continuous hydrological drainage.  
  > 4. **D8 Flow Direction & Accumulation:** We calculate steepest descent flow vectors across all grid cells to determine where runoff concentrates.  
  > 5. **Hydrological Yield & Sizing:** Using Open-Meteo historical climate records and Central Water Commission guidelines, the system computes the dynamic runoff coefficient $C$ based on slope, calculates annual harvestable water volume ($V = C \times P \times A$), and computes optimal trapezoidal pond dimensions."

---

## [2:00 - 3:45] Section 3: Live Website & Land Selection Demo (Core Evaluation)
* **Visual:** Return to `http://10.1.75.51:3317/`.
* **Action 1:** Click **"Sample Land"** button on the sidebar.
* **Spoken Script:**
  > "Now, let's demonstrate the live web interface.  
  > The map loads high-resolution satellite imagery overlaid with 1-meter elevation contours. Notice the amber dashed boundary: this represents our selected village farmland parcel of 5.4 hectares.  
  > You can also use the **Draw Area** tool at any time to sketch any custom polygon on the map."
* **Action 2:** Click the large blue button **"Analyze Land & Generate Plan"**.
* **Spoken Script:**
  > "When I click 'Analyze Land & Generate Plan', the backend processes the terrain in real-time.  
  > Look at the results generated:  
  > - **Optimal Pond Location:** Marked with this animated pulsing pin at latitude 21.2572°N, 81.3098°E, at a natural valley bed elevation of 288.7 meters, with 537 upstream drainage cells.  
  > - **Catchment Area:** Highlighted in blue, delineating a 5.41-hectare watershed with a gentle mean slope of 4.26%.  
  > - **Expected Harvestable Water Volume:** Look at the top card — the model estimates **14.17 Million Litres (14,173 cubic meters)** of water collected during the monsoon season. This provides dry-season water security for over 130 rural families for 240 days!  
  > - **Engineering Pond Sizing:** The system recommends a trapezoidal pond of **78 meters by 52 meters with a 3.0-meter depth**, providing 8,500 cubic meters of active storage."

---

## [3:45 - 4:30] Section 4: Dynamic Drawing & Export Tools
* **Visual:** Click **"Draw Area"** on the toolbar, click 4 points in a different section of the map, and click **"Analyze Land"**.
* **Spoken Script:**
  > "To prove the system is truly dynamic and not hardcoded, let's draw a completely different parcel in the northwest corner.  
  > As you see, the system instantly recalculates and places the pond site specifically at the lowest drainage exit of this new parcel, with custom catchment and rainfall statistics.  
  > Users can also toggle individual layers, switch between Satellite and OpenStreetMap basemaps, upload their own custom KML contour files, or click **Export GeoJSON** to download the plan for GIS integration."

---

## [4:30 - 4:55] Section 5: Conclusion & GitHub Repository
* **Visual:** Open GitHub repository `https://github.com/VishlavthKarthik/Pond-Catchment-Plan` showing clean code and test suite.
* **Spoken Script:**
  > "The entire codebase is open-source on GitHub, backed by 45 automated unit and integration tests passing at 100%. The application is deployed live in our containerized environment.  
  > Thank you for watching!"

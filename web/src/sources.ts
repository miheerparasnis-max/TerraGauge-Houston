/**
 * Every source the website cites, in one place, as APA 7 references with links.
 *
 * Each entry was checked against the publisher's record on 2026-11-15; the ledger is
 * docs/factcheck/2026-11-15-citation-check.md. Data sets that change over time carry the
 * date we retrieved them. `cite` is the APA in-text form used next to facts on the landing.
 */

export interface Ref {
  /** In-text citation, e.g. "Stork & Sneed, 2002". */
  cite: string;
  /** Author part, ending without a period. Organizations are written out. */
  author: string;
  /** "2022", "2019, March 21", or "n.d.". */
  date: string;
  /** Title; italic for stand-alone works (reports, data sets, web pages), roman for articles. */
  title: string;
  italicTitle: boolean;
  /** Text after the title, e.g. " (Version 1) [Data set]" or " (Fact Sheet 110-02)". */
  after?: string;
  /** Periodical (italic) with volume/issue/pages, or a publisher. */
  periodical?: string;
  volume?: string;
  issue?: string;
  pages?: string;
  publisher?: string;
  /** Data that change: "Retrieved November 7, 2026, from". */
  retrieved?: string;
  url: string;
}

export const REFS = {
  // ---- history and context on the landing ----
  storkSneed2002: {
    cite: "Stork & Sneed, 2002", author: "Stork, S. V., & Sneed, M.", date: "2002",
    title: "Houston-Galveston Bay area, Texas, from space: A new tool for mapping land subsidence", italicTitle: true, after: " (Fact Sheet 110-02)",
    publisher: "U.S. Geological Survey", url: "https://doi.org/10.3133/fs11002",
  },
  bernal2019: {
    cite: "Bernal, 2019", author: "Bernal, L.", date: "2019, March 21",
    title: "Brownwood: From neighborhood to nature center", italicTitle: false, periodical: "Houston History Magazine",
    url: "https://houstonhistorymagazine.org/2019/03/brownwood-from-neighborhood-to-nature-center/",
  },
  abc13_2021: {
    cite: "ABC13 Houston, 2021", author: "ABC13 Houston", date: "2021, June 26",
    title: "Subsidence blamed for disasters similar to Florida collapse", italicTitle: true,
    url: "https://abc13.com/subsidence-texas-what-is-sinking-ground/10831989/",
  },
  holt2021: {
    cite: "Holt, 2021", author: "Holt, V.", date: "2021, April 29",
    title: "Annual subsidence report shows Katy, Jersey Village with highest rate of ground sinking over time", italicTitle: false, periodical: "Community Impact",
    url: "https://communityimpact.com/houston/the-woodlands/2021/04/29/annual-subsidence-report-shows-katy-jersey-village-with-highest-rate-of-ground-sinking-over-time",
  },
  blakeZelinsky2018: {
    cite: "Blake & Zelinsky, 2018", author: "Blake, E. S., & Zelinsky, D. A.", date: "2018",
    title: "Tropical cyclone report: Hurricane Harvey (AL092017)", italicTitle: true,
    publisher: "National Hurricane Center", url: "https://www.nhc.noaa.gov/data/tcr/AL092017_Harvey.pdf",
  },
  lindnerFitzgerald2018: {
    cite: "Lindner & Fitzgerald, 2018", author: "Lindner, J., & Fitzgerald, S.", date: "2018",
    title: "Immediate report, final: Hurricane Harvey storm and flood information", italicTitle: true,
    publisher: "Harris County Flood Control District", url: "https://www.hcfcd.org/Portals/62/Harvey/immediate-flood-report-final-hurricane-harvey-2017.pdf",
  },

  // ---- data behind the map ----
  operaDisp: {
    cite: "OPERA Project, 2025", author: "OPERA Project, NASA Jet Propulsion Laboratory", date: "2025",
    title: "OPERA surface displacement from Sentinel-1 validated product", italicTitle: true, after: " (Version 1) [Data set]",
    publisher: "NASA Alaska Satellite Facility Distributed Active Archive Center", url: "https://doi.org/10.5067/SNWG/OPL3DISPS1-V1",
  },
  sentinel1: {
    cite: "European Space Agency, 2026", author: "European Space Agency", date: "2026",
    title: "Contains modified Copernicus Sentinel-1 data, 2016–2026", italicTitle: true, after: " [Data set]",
    url: "https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-1",
  },
  nisarGunw: {
    cite: "NISAR Project, 2026", author: "NISAR Project, NASA Jet Propulsion Laboratory & Indian Space Research Organisation", date: "2026",
    title: "NISAR L2 geocoded unwrapped interferogram, provisional", italicTitle: true, after: " (Version 1) [Data set]",
    publisher: "NASA Alaska Satellite Facility Distributed Active Archive Center",
    retrieved: "Retrieved November 10, 2026, from", url: "https://www.earthdata.nasa.gov/data/catalog/asf-nisar-l2-gunw-provisional-v1-1",
  },
  wang2022: {
    cite: "Wang et al., 2022", author: "Wang, G., Greuter, A., Petersen, C. M., & Turco, M. J.", date: "2022",
    title: "Houston GNSS network for subsidence and faulting monitoring: Data analysis methods and products", italicTitle: false,
    periodical: "Journal of Surveying Engineering", volume: "148", issue: "4", pages: "04022008", url: "https://doi.org/10.1061/(ASCE)SU.1943-5428.0000399",
  },
  houstonNet2024: {
    cite: "Harris-Galveston Subsidence District, 2024", author: "Harris-Galveston Subsidence District & University of Houston", date: "2024",
    title: "HoustonNet 2024 GNSS data release: Station summary table, 1993–2023", italicTitle: true, after: " [Data set]",
    url: "https://www.houstonnet.org/",
  },
  nwis: {
    cite: "U.S. Geological Survey, 2026", author: "U.S. Geological Survey", date: "2026",
    title: "USGS water data for the nation: National Water Information System database", italicTitle: true, after: " [Data set]",
    retrieved: "Retrieved November 7, 2026, from", url: "https://doi.org/10.5066/F7P55KJN",
  },
  ramageShah2024: {
    cite: "Ramage & Shah, 2024", author: "Ramage, J. K., & Shah, S. D.", date: "2024",
    title: "Cumulative compaction (from site activation through 2023) of subsurface sediments in the Chicot and Evangeline aquifers in the greater Houston area, Texas", italicTitle: true,
    after: " (Version 6.0) [Data set]", publisher: "U.S. Geological Survey", url: "https://doi.org/10.5066/P9YGUE2V",
  },
  garvin2018: {
    cite: "Garvin, 2018", author: "Garvin, K. M.", date: "2018",
    title: "Flood inundation geospatial data for the August and September 2017 flood event in Texas", italicTitle: true, after: " [Data set]",
    publisher: "U.S. Geological Survey", url: "https://doi.org/10.5066/F7VH5N3N",
  },
  fema: {
    cite: "Federal Emergency Management Agency, 2026", author: "Federal Emergency Management Agency", date: "2026",
    title: "National Flood Hazard Layer", italicTitle: true, after: " [Data set]",
    retrieved: "Retrieved November 7, 2026, from", url: "https://msc.fema.gov/nfhl",
  },
  nasadem: {
    cite: "NASA JPL, 2020", author: "NASA Jet Propulsion Laboratory", date: "2020",
    title: "NASADEM merged DEM global 1 arc second", italicTitle: true, after: " (Version 1) [Data set]",
    publisher: "NASA Land Processes Distributed Active Archive Center", url: "https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001",
  },
  dswx: {
    cite: "OPERA Project, 2024a", author: "OPERA Project, NASA Jet Propulsion Laboratory", date: "2024a",
    title: "OPERA dynamic surface water extent from Sentinel-1", italicTitle: true, after: " (Version 1) [Data set]",
    publisher: "NASA Physical Oceanography Distributed Active Archive Center", url: "https://doi.org/10.5067/OPDSWS1-L3V1",
  },
  dist: {
    cite: "OPERA Project, 2024b", author: "OPERA Project, NASA Jet Propulsion Laboratory", date: "2024b",
    title: "OPERA land surface disturbance alert from Harmonized Landsat Sentinel-2", italicTitle: true, after: " (Version 1) [Data set]",
    publisher: "NASA Land Processes Distributed Active Archive Center", url: "https://doi.org/10.5067/SNWG/OPERA_L3_DIST-ALERT-HLS_V1.001",
  },
  blackMarble: {
    cite: "Román et al., 2018", author: "Román, M. O., Wang, Z., Sun, Q., Kalb, V., Miller, S. D., Molthan, A., Schultz, L., Bell, J., Stokes, E. C., Pandey, B., Seto, K. C., Hall, D., Oda, T., Wolfe, R. E., Lin, G., Golpayegani, N., Devadiga, S., Davidson, C., Sarkar, S., … Masuoka, E. J.", date: "2018",
    title: "NASA's Black Marble nighttime lights product suite", italicTitle: false, periodical: "Remote Sensing of Environment", volume: "210", pages: "113–143",
    url: "https://doi.org/10.1016/j.rse.2018.03.017",
  },
  osm: {
    cite: "OpenStreetMap contributors, 2026", author: "OpenStreetMap contributors", date: "2026",
    title: "OpenStreetMap", italicTitle: true, after: " [Data set; place search by Nominatim; map tiles by OpenFreeMap and OpenMapTiles]",
    url: "https://www.openstreetmap.org/copyright",
  },
  sklearn: {
    cite: "Pedregosa et al., 2011", author: "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É.", date: "2011",
    title: "Scikit-learn: Machine learning in Python", italicTitle: false, periodical: "Journal of Machine Learning Research", volume: "12", pages: "2825–2830",
    url: "https://jmlr.org/papers/v12/pedregosa11a.html",
  },

  // ---- hardware ----
  hohensinn2022: {
    cite: "Hohensinn et al., 2022", author: "Hohensinn, R., Stauffer, R., Glaner, M. F., Herrera Pinzón, I. D., Vuadens, E., Rossi, Y., Clinton, J., & Rothacher, M.", date: "2022",
    title: "Low-cost GNSS and real-time PPP: Assessing the precision of the u-blox ZED-F9P for kinematic monitoring applications", italicTitle: false,
    periodical: "Remote Sensing", volume: "14", issue: "20", pages: "5100", url: "https://doi.org/10.3390/rs14205100",
  },
  cors: {
    cite: "National Geodetic Survey, 2026", author: "National Geodetic Survey", date: "2026",
    title: "NOAA Continuously Operating Reference Station (CORS) network data, stations NETP and ZHU1", italicTitle: true, after: " [Data set]",
    publisher: "NOAA Open Data Dissemination Program", retrieved: "Retrieved November 15, 2026, from", url: "https://noaa-cors-pds.s3.amazonaws.com/index.html",
  },
  cnes: {
    cite: "Centre National d'Études Spatiales, 2026", author: "Centre National d'Études Spatiales", date: "2026",
    title: "PPP-Wizard real-time multi-GNSS orbits, clocks and signal biases, GPS week 2444 day 6", italicTitle: true, after: " [Data set]",
    retrieved: "Retrieved November 15, 2026, from", url: "http://www.ppp-wizard.net/products/REAL_TIME/",
  },
  rtklib: {
    cite: "rtklibexplorer, 2026", author: "rtklibexplorer", date: "2026",
    title: "RTKLIB-EX", italicTitle: true, after: " (Version 2.5.1) [Computer software; based on RTKLIB by T. Takasu]",
    publisher: "GitHub", url: "https://github.com/rtklibexplorer/RTKLIB",
  },
} satisfies Record<string, Ref>;

export type RefKey = keyof typeof REFS;

/** Sort references the APA way: by author, then date. */
export const sortRefs = (keys: RefKey[]) => [...keys].sort((a, b) => (REFS[a].author + REFS[a].date).localeCompare(REFS[b].author + REFS[b].date));

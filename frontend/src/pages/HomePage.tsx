import { Search, Sparkles, ShoppingBag, ArrowRight } from "lucide-react";
import { useHashMode } from "../hooks/useHashMode";
import "../styles/home.css";

interface RecentDrill {
  id: string;
  title: string;
  description: string;
  category: string;
  thumbnail?: string;
}

export default function HomePage() {
  const { switchMode } = useHashMode();

  // Sample recent drills - in production, this would come from an API
  const recentDrills: RecentDrill[] = [
    {
      id: "1",
      title: "Mechanical Escapements",
      description: "Deep dive into the precision engineering of luxury chronometers.",
      category: "TECH",
      thumbnail: "linear-gradient(135deg, #8B7355, #D4AF37)",
    },
    {
      id: "2",
      title: "Global Supply Chains",
      description: "Analysis of semiconductor flow across major Asian hubs.",
      category: "MARKET",
      thumbnail: "linear-gradient(135deg, #1a1a2e, #ff6b35)",
    },
    {
      id: "3",
      title: "Next-Gen Cooling",
      description: "Liquid immersion techniques for high-density computer clusters.",
      category: "INFRA",
      thumbnail: "linear-gradient(135deg, #0a0a2e, #16213e)",
    },
  ];

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    switchMode("explainer");
  };

  return (
    <div className="home-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <h1 className="hero-title">
            <span className="hero-title-white">Drill</span>
            <span className="hero-title-orange">Down</span>
          </h1>
          <p className="hero-subtitle">
            Analyze deeper. From high-level concepts to granular technical specs in milliseconds.
          </p>

          {/* Search Bar */}
          <form className="search-bar" onSubmit={handleSearch}>
            <div className="search-input-wrapper">
              <Search size={20} className="search-icon" />
              <input
                type="text"
                placeholder="What are we exploring today?"
                className="search-input"
              />
            </div>
            <button type="submit" className="search-button">
              DRILL
            </button>
          </form>

          {/* Mode Shortcuts */}
          <div className="mode-shortcuts">
            <button
              className="mode-shortcut"
              onClick={() => switchMode("explainer")}
              title="Go to Explainer mode"
            >
              <Sparkles size={18} strokeWidth={1.5} />
              Explainer Mode
            </button>
            <button
              className="mode-shortcut"
              onClick={() => switchMode("ecommerce")}
              title="Go to Ecommerce mode"
            >
              <ShoppingBag size={18} strokeWidth={1.5} />
              Ecommerce Mode
            </button>
          </div>
        </div>
      </section>

      {/* Recent Drills Section */}
      <section className="recent-drills-section">
        <div className="section-header">
          <h2 className="section-title">Recent Drills</h2>
          <button className="view-all-btn">
            View All
            <ArrowRight size={16} strokeWidth={1.5} />
          </button>
        </div>

        <div className="drills-grid">
          {recentDrills.map((drill) => (
            <article key={drill.id} className="drill-card">
              <div
                className="drill-card-thumbnail"
                style={{ background: drill.thumbnail }}
              >
                <div className="drill-card-overlay" />
              </div>
              <div className="drill-card-content">
                <span className="drill-category">{drill.category}</span>
                <h3 className="drill-title">{drill.title}</h3>
                <p className="drill-description">{drill.description}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { logout } from "../data/api/auth.api";
import { useAuthSession } from "../features/auth/useAuthSession";
import "./home-page.css";

type PillTone = "fastest" | "focus" | "improved" | "live" | "ready" | "soon";

type Stat = {
  value: string;
  label: string;
  description: string;
};

type Destination = {
  title: string;
  body: string;
  to: string;
  action: string;
  pill: string;
  tone: PillTone;
  highlights: string[];
};

type StoryCard = {
  tag: string;
  title: string;
  meta: string;
};

type StandingRow = {
  position: string;
  driver: string;
  team: string;
  points: string;
  pill: string;
  tone: PillTone;
};

type ArchiveItem = {
  round: string;
  title: string;
  note: string;
};

const liveRaceActive = false;

const heroStats: Stat[] = [
  {
    value: "24",
    label: "Race weekends",
    description: "Move through the full season and jump back into any weekend from one archive.",
  },
  {
    value: "20",
    label: "Drivers tracked",
    description: "Keep the championship picture close whether the circuit is live or quiet.",
  },
  {
    value: "10",
    label: "Teams in view",
    description: "Follow constructor momentum, storylines, and session context in one place.",
  },
];

const destinations: Destination[] = [
  {
    title: "Live Race",
    body: "Open the race workspace for timing, gaps, tyre windows, and incident context the moment a session goes green.",
    to: "/live",
    action: "Open live race",
    pill: liveRaceActive ? "Live now" : "Preview",
    tone: liveRaceActive ? "live" : "focus",
    highlights: ["Timing tower", "Tyre windows", "Gap tracking"],
  },
  {
    title: "Story Feed",
    body: "A news wall for official F1 videos, headlines, and the latest paddock conversation between sessions.",
    to: "/story-feed",
    action: "Open story feed",
    pill: "News wall",
    tone: "improved",
    highlights: ["F1 YouTube", "Headlines", "Weekend notes"],
  },
  {
    title: "Session Explorer",
    body: "Revisit previous races, qualifying sessions, and complete weekends without losing the bigger season context.",
    to: "/sessions",
    action: "Browse sessions",
    pill: "Archive",
    tone: "ready",
    highlights: ["Session import", "Layout workspace", "Replay mode"],
  },
  {
    title: "Standings",
    body: "Keep driver and constructor tables close, especially when there is no live race to follow on the front page.",
    to: "/standings",
    action: "Open standings",
    pill: "Season view",
    tone: "focus",
    highlights: ["Drivers", "Constructors", "Points view"],
  },
];

const storyCards: StoryCard[] = [
  {
    tag: "Video",
    title: "Official race recaps, team radio highlights, and paddock interviews will land here.",
    meta: "F1 channel wall",
  },
  {
    tag: "Headline",
    title: "Weekend talking points, post-session notes, and major storylines will stack into one feed.",
    meta: "News wall",
  },
  {
    tag: "Watch next",
    title: "Feature videos, analysis clips, and press moments can sit alongside session context.",
    meta: "Editorial surface",
  },
];

const archiveItems: ArchiveItem[] = [
  {
    round: "R01",
    title: "Bahrain Grand Prix",
    note: "Race, qualifying, practice sessions, and weekend context.",
  },
  {
    round: "R02",
    title: "Saudi Arabian Grand Prix",
    note: "Fast jump-in points for each session and race recap.",
  },
  {
    round: "R03",
    title: "Australian Grand Prix",
    note: "Previous weekend replay surface with room for detail later on.",
  },
];

const standingsRows: StandingRow[] = [
  {
    position: "P1",
    driver: "VER",
    team: "Red Bull",
    points: "26",
    pill: "Leader",
    tone: "fastest",
  },
  {
    position: "P2",
    driver: "LEC",
    team: "Ferrari",
    points: "18",
    pill: "Chasing",
    tone: "focus",
  },
  {
    position: "P3",
    driver: "NOR",
    team: "McLaren",
    points: "15",
    pill: "In touch",
    tone: "improved",
  },
  {
    position: "P4",
    driver: "SAI",
    team: "Ferrari",
    points: "12",
    pill: "In touch",
    tone: "ready",
  },
];

const livePreviewRows: StandingRow[] = [
  {
    position: "P1",
    driver: "VER",
    team: "Red Bull",
    points: "1:18.432",
    pill: "Fastest lap",
    tone: "fastest",
  },
  {
    position: "P2",
    driver: "NOR",
    team: "McLaren",
    points: "+0.189",
    pill: "Improving",
    tone: "improved",
  },
  {
    position: "P3",
    driver: "LEC",
    team: "Ferrari",
    points: "+0.312",
    pill: "Sector best",
    tone: "focus",
  },
];

function Pill({ label, tone }: { label: string; tone: PillTone }) {
  return <span className={`ui-pill ui-pill--${tone}`}>{label}</span>;
}

function HeroFocusPanel() {
  const rows = liveRaceActive ? livePreviewRows : standingsRows;

  return (
    <aside className="surface-card home-preview">
      <div className="home-preview__header">
        <div>
          <p className="home-preview__eyebrow">
            {liveRaceActive ? "Race weekend" : "Season snapshot"}
          </p>
          <h2 className="home-preview__title">
            {liveRaceActive ? "Live Race" : "Standings"}
          </h2>
          <p className="home-preview__subtitle">
            {liveRaceActive
              ? "Timing, gaps, and key moments stay front and center while the race is running."
              : "When there is no active session, the home focus shifts to the championship picture."}
          </p>
        </div>

        <Pill
          label={liveRaceActive ? "Race mode" : "Off-session"}
          tone={liveRaceActive ? "live" : "focus"}
        />
      </div>

      <div className="home-preview__meta">
        <div className="home-preview__meta-card">
          <span className="home-preview__meta-label">
            {liveRaceActive ? "Session" : "Drivers leader"}
          </span>
          <span className="home-preview__meta-value numeric-font">
            {liveRaceActive ? "Lap 43 / 58" : "VER 26 PTS"}
          </span>
        </div>
        <div className="home-preview__meta-card">
          <span className="home-preview__meta-label">
            {liveRaceActive ? "Tyre focus" : "Constructors leader"}
          </span>
          <span className="home-preview__meta-value numeric-font">
            {liveRaceActive ? "Medium stint" : "Ferrari 30 PTS"}
          </span>
        </div>
        <div className="home-preview__meta-card">
          <span className="home-preview__meta-label">
            {liveRaceActive ? "Interval" : "Next live mode"}
          </span>
          <span className="home-preview__meta-value numeric-font">
            {liveRaceActive ? "+0.189" : "Race weekend"}
          </span>
        </div>
      </div>

      <div className="home-preview__board">
        {rows.map((row) => (
          <div key={row.driver} className="home-preview__row" data-tone={row.tone}>
            <span className="home-preview__position numeric-font">{row.position}</span>

            <div className="home-preview__driver">
              <span className="home-preview__driver-name">{row.driver}</span>
              <span className="home-preview__driver-team">{row.team}</span>
            </div>

            <div className="home-preview__lap">
              <span className="home-preview__lap-time numeric-font">{row.points}</span>
              <span className="home-preview__lap-delta">
                {liveRaceActive ? "Gap to lead" : "Championship points"}
              </span>
            </div>

            <Pill label={row.pill} tone={row.tone} />
          </div>
        ))}
      </div>

      <div className="home-preview__footer">
        <div className="home-preview__footer-item">
          <span className="home-preview__footer-label">
            {liveRaceActive ? "Pinned surface" : "Best fallback"}
          </span>
          <span className="home-preview__footer-value">
            {liveRaceActive ? "Live Race" : "Standings"}
          </span>
        </div>
        <div className="home-preview__footer-item">
          <span className="home-preview__footer-label">
            {liveRaceActive ? "Next stop" : "Quick jump"}
          </span>
          <span className="home-preview__footer-value">Story Feed</span>
        </div>
      </div>
    </aside>
  );
}

export function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading } = useAuthSession();
  const isAuthenticated = data?.authenticated === true;

  async function handleLogout() {
    logout();

    queryClient.setQueryData(["auth-session"], {
      authenticated: false,
      user_id: null,
      email: null,
    });

    await queryClient.invalidateQueries({ queryKey: ["auth-session"] });

    navigate("/login");
  }

  return (
    <div className="home-page">
      <section className="home-page__hero">
        <div className="surface-card home-hero__copy">
          <div className="home-hero__eyebrow">
            <Pill label={liveRaceActive ? "Live race" : "Season hub"} tone={liveRaceActive ? "live" : "focus"} />
            <span>
              Follow the weekend live, scan the news wall between sessions, rewind old races,
              and keep the championship table close.
            </span>
          </div>

          <h1 className="home-hero__title">Live Race. Story Wall. Session Archive. Season Standings.</h1>

          <p className="home-hero__lead">
            Pitwall Insights is built to keep motorsport context in one place. Open the
            live race when the circuit is active, drop into a story feed shaped like a
            news wall when the track goes quiet, explore previous weekends, and move
            straight to the drivers and constructors tables.
          </p>

          <div className="home-hero__actions">
            <Link to="/live" className="button-primary">
              Open live race
            </Link>
            <Link to="/story-feed" className="button-secondary">
              Open story feed
            </Link>
            <Link to="/sessions" className="button-secondary">
              Browse sessions
            </Link>
          </div>

          <div className="home-hero__stats">
            {heroStats.map((stat) => (
              <article key={stat.label} className="home-stat-card">
                <p className="home-stat-card__value numeric-font">{stat.value}</p>
                <span className="home-stat-card__label">{stat.label}</span>
                <p className="home-stat-card__description">{stat.description}</p>
              </article>
            ))}
          </div>
        </div>

        <HeroFocusPanel />
      </section>

      <section className="home-section">
        <div className="home-section__header">
          <div className="home-section__heading">
            <Pill label="Explore" tone="ready" />
            <h2 className="home-section__title">Choose the surface you want first</h2>
            <p className="home-section__lead">
              The home page should feel like a fast launch point into the parts of the
              product that matter most during and between race weekends.
            </p>
          </div>
        </div>

        <div className="home-destination-grid">
          {destinations.map((destination) => (
            <article key={destination.title} className="surface-card home-destination-card">
              <div className="home-destination-card__header">
                <Pill label={destination.pill} tone={destination.tone} />
              </div>
              <h3 className="home-destination-card__title">{destination.title}</h3>
              <p className="home-destination-card__body">{destination.body}</p>
              <div className="home-destination-card__meta">
                {destination.highlights.map((highlight) => (
                  <span key={highlight} className="home-destination-card__meta-item">
                    {highlight}
                  </span>
                ))}
              </div>
              <Link to={destination.to} className="home-destination-card__link">
                {destination.action}
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="home-section home-section--content">
        <article className="surface-card home-story-wall">
          <div className="home-section__header">
            <div className="home-section__heading">
              <Pill label="Story Feed" tone="improved" />
              <h2 className="home-section__title">A news wall for the race weekend</h2>
              <p className="home-section__lead">
                Official F1 videos, breaking headlines, and storylines from the paddock
                should live in one feed that feels as useful between sessions as live timing
                does on race day.
              </p>
            </div>
          </div>

          <div className="home-story-wall__list">
            {storyCards.map((card) => (
              <article key={card.title} className="home-story-wall__item">
                <span className="home-story-wall__tag">{card.tag}</span>
                <h3 className="home-story-wall__item-title">{card.title}</h3>
                <p className="home-story-wall__item-meta">{card.meta}</p>
              </article>
            ))}
          </div>

          <Link to="/story-feed" className="button-secondary">
            Open story feed preview
          </Link>
        </article>

        <div className="home-stack">
          <article className="surface-card home-panel">
            <Pill label="Session Explorer" tone="soon" />
            <h2 className="home-panel__title">Look back at previous races</h2>
            <p className="home-panel__body">
              The session archive should make it easy to jump through past weekends and
              pick up race, qualifying, or practice context without digging.
            </p>

            <ul className="home-list">
              {archiveItems.map((item) => (
                <li key={item.title} className="home-list__item">
                  <span className="home-list__item-title">
                    <span className="numeric-font">{item.round}</span> {item.title}
                  </span>
                  <span className="home-list__item-body">{item.note}</span>
                </li>
              ))}
            </ul>

            <Link to="/sessions" className="home-panel__link">
              Open session explorer
            </Link>
          </article>

          <article className="surface-card home-panel">
            <Pill label="Standings" tone="focus" />
            <h2 className="home-panel__title">Keep the season table within reach</h2>
            <p className="home-panel__body">
              When there is no live race running, standings become the quickest way to see
              who owns the moment across drivers and constructors.
            </p>

            <div className="home-standings-list">
              {standingsRows.map((row) => (
                <div key={row.driver} className="home-standings-row">
                  <span className="home-standings-row__position numeric-font">{row.position}</span>
                  <div className="home-standings-row__driver">
                    <span className="home-standings-row__name">{row.driver}</span>
                    <span className="home-standings-row__team">{row.team}</span>
                  </div>
                  <span className="home-standings-row__points numeric-font">{row.points}</span>
                </div>
              ))}
            </div>

            <Link to="/standings" className="home-panel__link">
              Open standings
            </Link>
          </article>
        </div>
      </section>

      <section className="home-section">
        <div className="surface-card home-final-cta">
          <div className="home-final-cta__copy">
            <Pill
              label={isAuthenticated ? "Signed in" : "Pitwall access"}
              tone={isAuthenticated ? "ready" : "ready"}
            />
            <h2 className="home-final-cta__title">Pick up the weekend from any angle.</h2>
            <p className="home-final-cta__body">
              {isAuthenticated
                ? `You are signed in${data?.email ? ` as ${data.email}` : ""}. Jump straight into the live race, the story wall, the session archive, or sign out when you are done.`
                : "Start with the live race, drop into the story wall, move through the session archive, or keep the standings nearby as the season takes shape."}
            </p>
          </div>

          <div className="home-final-cta__actions">
            {isLoading ? (
              <span className="button-secondary">Checking session...</span>
            ) : isAuthenticated ? (
              <>
                <Link to="/live" className="button-primary">
                  Open live race
                </Link>
                <button onClick={handleLogout} className="button-secondary">
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="button-secondary">
                  Sign in
                </Link>
                <Link to="/signup" className="button-primary">
                  Create account
                </Link>
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

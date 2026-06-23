import { useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { apiDelete, apiFormPost, apiGet, apiPost, assetUrl, setAuthToken } from "./services/api";

const BRAND_LIST = ["Nike", "Adidas", "Puma", "Reebok", "Skechers", "Bata", "Woodland", "Campus"];
const CATEGORY_LIST = ["Running Shoes", "Casual Shoes", "Sports Shoes", "Formal Shoes", "Sneakers", "Sandals"];
const SIZE_LIST = ["6", "7", "8", "9", "10"];
const REQUIRED_VOICE_SAMPLES = 5;
const CATEGORY_QUERY = {
  "Running Shoes": "single-running-shoe",
  "Casual Shoes": "single-casual-shoe",
  "Sports Shoes": "single-sports-shoe",
  "Formal Shoes": "single-formal-shoe",
  Sneakers: "single-sneaker",
  Sandals: "single-sandal-chappal",
};

function inferBrand(name = "") {
  const found = BRAND_LIST.find((brand) => name.toLowerCase().includes(brand.toLowerCase()));
  return found || "Footwear";
}

function inferCategory(name = "", description = "") {
  const text = `${name} ${description}`.toLowerCase();
  if (text.includes("running")) return "Running Shoes";
  if (text.includes("casual")) return "Casual Shoes";
  if (text.includes("sports")) return "Sports Shoes";
  if (text.includes("formal")) return "Formal Shoes";
  if (text.includes("sandal") || text.includes("chappal")) return "Sandals";
  return "Sneakers";
}

function inferSize(name = "") {
  const m = name.match(/size\s*(\d{1,2})/i);
  return m ? m[1] : "8";
}

function imageForProduct(product) {
  const firstImage = Array.isArray(product.images) ? product.images[0] : "";
  if (firstImage) return assetUrl(firstImage);
  const category = inferCategory(product.name, product.description);
  return `https://source.unsplash.com/900x700/?${encodeURIComponent(CATEGORY_QUERY[category] || "single-footwear-shoe")}&sig=${product.id}`;
}

function getSpeechLanguage(language) {
  if (language === "hi") return "hi-IN";
  if (language === "kn") return "kn-IN";
  return "en-IN";
}

function pickSpeechVoice(language) {
  if (!window.speechSynthesis) return null;
  const lang = getSpeechLanguage(language).toLowerCase();
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => (v.lang || "").toLowerCase() === lang) ||
    voices.find((v) => (v.lang || "").toLowerCase().startsWith(lang.slice(0, 2))) ||
    voices.find((v) => (v.lang || "").toLowerCase().startsWith("en")) ||
    null
  );
}

function speak(text, language) {
  void speakAsync(text, language);
}

function speakAsync(text, language) {
  return new Promise((resolve) => {
    if (!text || !window.speechSynthesis) {
      resolve();
      return;
    }
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = getSpeechLanguage(language);
    utter.rate = 1.02;
    utter.pitch = 1;
    utter.volume = 1;
    const voice = pickSpeechVoice(language);
    if (voice) utter.voice = voice;

    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      resolve();
    };
    const timeout = window.setTimeout(finish, Math.min(Math.max(text.length * 70, 1200), 6500));
    utter.onend = () => {
      window.clearTimeout(timeout);
      finish();
    };
    utter.onerror = () => {
      window.clearTimeout(timeout);
      finish();
    };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  });
}

function localizedClientMessage(language, key) {
  const lang = language === "hi" ? "hi" : language === "kn" ? "kn" : "en";
  const messages = {
    orderSuccess: {
      en: "Thanks for ordering in StrideSphere. Your order is successful and now processing.",
      hi: "StrideSphere mein order karne ke liye dhanyavaad. Aapka order successful hai aur processing mein hai.",
      kn: "StrideSphere alli order madiddakke dhanyavaadagalu. Nimma order successful aagide mattu processing aaguttide.",
    },
    speakClearly: {
      en: "Please speak clearly.",
      hi: "Kripya clearly boliye.",
      kn: "Dayavittu clear aagi heli.",
    },
  };
  return messages[key][lang];
}

function AuthView({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    try {
      if (mode === "register") {
        await apiPost("/auth/register", { email, password });
      }
      const login = await apiPost("/auth/login", { email, password });
      setAuthToken(login.access_token);
      onAuth({ token: login.access_token, userId: String(login.user_id), email });
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="min-h-screen page-bg flex items-center justify-center px-4">
      <div className="glass-panel w-full max-w-md p-6">
        <h1 className="brand-heading text-3xl font-semibold">StrideSphere</h1>
        <p className="mt-1 text-sm text-slate-300">Secure login for voice-authenticated shopping</p>
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button className={`btn-secondary ${mode === "login" ? "ring-1 ring-cyan-300/70" : ""}`} onClick={() => setMode("login")}>Login</button>
          <button className={`btn-secondary ${mode === "register" ? "ring-1 ring-cyan-300/70" : ""}`} onClick={() => setMode("register")}>Register</button>
        </div>
        <input className="input-chip mt-4 w-full" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="input-chip mt-2 w-full" placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error ? <p className="mt-2 text-sm text-rose-300">{error}</p> : null}
        <button className="btn-primary mt-4 w-full" onClick={() => void submit()}>{mode === "login" ? "Login" : "Register + Login"}</button>
      </div>
    </div>
  );
}

function Header({ userEmail, userId, voiceEnabled, voiceProfileId, onLogout, onOpenSettings, onToggleVoice }) {
  return (
    <header className="glass-panel mb-6 flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-cyan-300">Voice Secure Footwear Commerce</p>
        <h1 className="brand-heading mt-1 text-3xl font-semibold md:text-4xl">StrideSphere</h1>
        <p className="mt-1 text-sm text-slate-300">{userEmail} • User ID {userId}</p>
        <p className="mt-1 text-xs text-slate-400">Voice ID: {voiceProfileId || "Not enrolled"}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className={`btn-secondary ${voiceEnabled ? "ring-1 ring-emerald-300/70" : ""}`} onClick={onToggleVoice}>
          Voice {voiceEnabled ? "On" : "Off"}
        </button>
        <button className="btn-secondary" onClick={onOpenSettings}>Settings</button>
        <button className="btn-secondary" onClick={onLogout}>Logout</button>
      </div>
    </header>
  );
}

function SettingsPanel({ open, onClose, voiceEnabled, setVoiceEnabled, language, setLanguage, sampleIds, onCaptureSample, onResetSamples, voiceProfileId }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 bg-black/45 p-4">
      <div className="glass-panel mx-auto max-w-lg p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Voice Settings</h3>
          <button className="btn-secondary" onClick={onClose}>Close</button>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={voiceEnabled} onChange={(e) => setVoiceEnabled(e.target.checked)} />
          Enable voice commands for ordering
        </label>
        <label className="mt-3 block text-sm text-slate-300">Assistant language</label>
        <select className="input-chip mt-1 w-full" value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="en">English</option>
          <option value="hi">Hindi</option>
          <option value="kn">Kannada</option>
        </select>
        <div className="mt-4 rounded-xl border border-white/15 bg-slate-900/70 p-3">
          <p className="text-sm">Voice Enrollment Samples: {sampleIds.length}/{REQUIRED_VOICE_SAMPLES}</p>
          <p className="text-xs text-slate-400">Capture {REQUIRED_VOICE_SAMPLES} clear samples of your voice. Unique Voice ID will be generated automatically.</p>
          <div className="mt-3 flex gap-2">
            <button className="btn-primary" onClick={() => void onCaptureSample()} disabled={sampleIds.length >= REQUIRED_VOICE_SAMPLES}>Capture Sample</button>
            <button className="btn-secondary" onClick={() => void onResetSamples()} title="Reset voice samples">Reset Samples</button>
          </div>
          <p className="mt-3 text-xs text-cyan-200">Voice Profile ID: {voiceProfileId || "-"}</p>
        </div>
      </div>
    </div>
  );
}

function NavBar() {
  const links = [
    { to: "/", label: "Shop" },
    { to: "/wishlist", label: "Wishlist" },
    { to: "/cart", label: "Cart" },
    { to: "/checkout", label: "Checkout" },
  ];
  return (
    <nav className="glass-panel mb-6 flex flex-wrap items-center gap-2 p-3">
      {links.map((link) => (
        <NavLink key={link.to} to={link.to} end className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}>
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}

function ShopPage(props) {
  const { products, recommendedProducts, search, setSearch, brandFilter, setBrandFilter, categoryFilter, setCategoryFilter, sizeFilter, setSizeFilter, wishlist, onToggleWishlist, onAdd, onBuy } = props;
  return (
    <section className="glass-panel p-4">
      <div className="mb-4 flex flex-wrap gap-3">
        <input className="input-chip min-w-[220px] flex-1" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search shoes..." />
        <select className="input-chip" value={brandFilter} onChange={(e) => setBrandFilter(e.target.value)}><option>All</option>{BRAND_LIST.map((b) => <option key={b}>{b}</option>)}</select>
        <select className="input-chip" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}><option>All</option>{CATEGORY_LIST.map((c) => <option key={c}>{c}</option>)}</select>
        <select className="input-chip" value={sizeFilter} onChange={(e) => setSizeFilter(e.target.value)}><option>All</option>{SIZE_LIST.map((s) => <option key={s}>{s}</option>)}</select>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {products.map((p) => (
          <article key={p.id} className="card-fade rounded-2xl border border-white/15 bg-slate-900/70 p-3">
            <img src={imageForProduct(p)} alt={p.name} className="h-48 w-full rounded-xl object-cover" loading="lazy" />
            <h3 className="mt-3 text-sm font-semibold">{p.name}</h3>
            <p className="mt-1 text-xs text-slate-300">{inferBrand(p.name)} • {inferCategory(p.name, p.description)} • Size {inferSize(p.name)}</p>
            <p className="mt-2 text-lg font-semibold text-cyan-300">Rs.{Number(p.price).toFixed(0)}</p>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <button className="btn-primary" onClick={() => onAdd(p)}>Add</button>
              <button className="btn-secondary" onClick={() => onToggleWishlist(p.id)}>{wishlist.includes(p.id) ? "Saved" : "Wishlist"}</button>
              <button className="btn-accent" onClick={() => onBuy(p)}>Buy Now</button>
            </div>
          </article>
        ))}
      </div>
      {recommendedProducts?.length ? (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold text-cyan-200">Recommended For You</h3>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {recommendedProducts.slice(0, 5).map((p) => (
              <button key={`rec-${p.id}`} className="rounded-xl border border-cyan-300/30 bg-cyan-900/20 p-2 text-left" onClick={() => onAdd(p)}>
                <p className="truncate text-xs font-semibold">{p.name}</p>
                <p className="text-xs text-cyan-100">Rs.{Number(p.price).toFixed(0)}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function WishlistPage({ items, onAdd, onToggleWishlist, onBuy }) {
  return (
    <section className="glass-panel p-4">
      <h2 className="mb-3 text-xl font-semibold">Wishlist</h2>
      {!items.length ? <p className="text-slate-300">No wishlist items.</p> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((p) => (
            <article key={p.id} className="rounded-2xl border border-white/15 bg-slate-900/70 p-3">
              <img src={imageForProduct(p)} alt={p.name} className="h-44 w-full rounded-xl object-cover" />
              <h3 className="mt-3 text-sm font-semibold">{p.name}</h3>
              <p className="mt-1 text-xs text-slate-300">{inferCategory(p.name, p.description)} • Size {inferSize(p.name)}</p>
              <p className="mt-2 text-lg font-semibold text-cyan-300">Rs.{Number(p.price).toFixed(0)}</p>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <button className="btn-primary" onClick={() => onAdd(p)}>Add</button>
                <button className="btn-secondary" onClick={() => onToggleWishlist(p.id)}>Remove</button>
                <button className="btn-accent" onClick={() => onBuy(p)}>Buy Now</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function CartPage({ cart, onRemove, onGoCheckout }) {
  return (
    <section className="glass-panel p-4">
      <h2 className="mb-3 text-xl font-semibold">Cart</h2>
      {!cart.items?.length ? <p className="text-slate-300">Cart is empty.</p> : (
        <div className="space-y-3">
          {cart.items.map((item) => (
            <div key={`${item.id}-${item.product_id}`} className="rounded-xl border border-white/15 bg-slate-900/70 p-3">
              <p className="text-sm font-semibold">{item.name || `Product ${item.product_id}`}</p>
              <p className="text-xs text-slate-300">Qty {item.quantity} • Rs.{item.line_total}</p>
              <button className="mt-2 text-xs text-rose-300 hover:text-rose-200" onClick={() => onRemove(item.product_id)}>Remove</button>
            </div>
          ))}
          <div className="rounded-xl border border-cyan-300/30 bg-cyan-900/20 p-3">
            <p className="text-sm font-semibold">Total: Rs.{Number(cart.total_amount || 0).toFixed(0)}</p>
            <button className="btn-primary mt-3 w-full" onClick={onGoCheckout}>Proceed To Checkout</button>
          </div>
        </div>
      )}
    </section>
  );
}

function CheckoutPage({ cart, payMode, setPayMode, otp, setOtp, checkoutDetails, setCheckoutDetails, onCheckout, orderStatus, lastOrder }) {
  const pricing = lastOrder?.pricing || {};
  const delivery = lastOrder?.delivery || {};
  const payment = lastOrder?.payment || {};

  function updateCustomer(field, value) {
    setCheckoutDetails((prev) => ({ ...prev, customer: { ...prev.customer, [field]: value } }));
  }

  function updateDelivery(field, value) {
    setCheckoutDetails((prev) => ({ ...prev, delivery: { ...prev.delivery, [field]: value } }));
  }

  return (
    <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <div className="glass-panel p-4">
        <h2 className="text-xl font-semibold">Checkout</h2>
        <div className="mt-3 rounded-xl border border-white/15 bg-slate-900/70 p-4">
          <p className="text-sm">Items: {cart.items?.length || 0}</p>
          <p className="text-sm">Amount: Rs.{Number(cart.total_amount || 0).toFixed(0)}</p>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <input className="input-chip" value={checkoutDetails.customer.name} onChange={(e) => updateCustomer("name", e.target.value)} placeholder="Customer name" />
          <input className="input-chip" value={checkoutDetails.customer.phone} onChange={(e) => updateCustomer("phone", e.target.value)} placeholder="Phone" />
          <input className="input-chip md:col-span-2" value={checkoutDetails.delivery.address} onChange={(e) => updateDelivery("address", e.target.value)} placeholder="Delivery address" />
          <input className="input-chip" value={checkoutDetails.delivery.city} onChange={(e) => updateDelivery("city", e.target.value)} placeholder="City" />
          <input className="input-chip" value={checkoutDetails.delivery.pincode} onChange={(e) => updateDelivery("pincode", e.target.value)} placeholder="Pincode" />
        </div>
        {lastOrder ? (
          <div className="mt-5 space-y-4">
            <div className="rounded-xl border border-emerald-300/40 bg-emerald-900/25 p-4">
              <h3 className="text-lg font-semibold text-emerald-200">Order Placed Successfully</h3>
              <p className="mt-1 text-sm text-slate-200">Order ID: {lastOrder.order_id}</p>
              <p className="text-sm text-slate-300">Date: {lastOrder.created_at}</p>
              <p className="text-sm text-slate-300">Status: {delivery.status || "Processing"}</p>
            </div>

            <div className="overflow-x-auto rounded-xl border border-white/15">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-950/70 text-slate-300">
                  <tr>
                    <th className="p-3">Name</th>
                    <th className="p-3">Quantity</th>
                    <th className="p-3">Price</th>
                    <th className="p-3">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(lastOrder.items || []).map((item) => (
                    <tr key={`${item.product_id}-${item.name}`} className="border-t border-white/10">
                      <td className="p-3">{item.name}</td>
                      <td className="p-3">{item.quantity}</td>
                      <td className="p-3">Rs.{Number(item.price).toFixed(2)}</td>
                      <td className="p-3">Rs.{Number(item.total).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-white/15 bg-slate-900/70 p-4 text-sm">
                <h3 className="mb-2 font-semibold">Price Breakdown</h3>
                <p>Subtotal: Rs.{Number(pricing.subtotal || 0).toFixed(2)}</p>
                <p>Tax: Rs.{Number(pricing.tax || 0).toFixed(2)}</p>
                <p>Delivery: Rs.{Number(pricing.delivery_fee || 0).toFixed(2)}</p>
                <p>Discount: Rs.{Number(pricing.discount || 0).toFixed(2)}</p>
                <p className="mt-2 text-lg font-semibold text-cyan-200">Grand Total: Rs.{Number(pricing.grand_total || 0).toFixed(2)}</p>
              </div>
              <div className="rounded-xl border border-white/15 bg-slate-900/70 p-4 text-sm">
                <h3 className="mb-2 font-semibold">Delivery & Payment</h3>
                <p>{delivery.address}</p>
                <p>{delivery.city} - {delivery.pincode}</p>
                <p className="mt-2">Method: {payment.method}</p>
                <p>Status: {payment.status}</p>
              </div>
            </div>

            <div className="rounded-xl border border-white/15 bg-slate-950/80 p-4">
              <h3 className="mb-2 font-semibold">Invoice</h3>
              <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-slate-200">{lastOrder.invoice_text}</pre>
            </div>
          </div>
        ) : null}
      </div>
      <div className="glass-panel p-4">
        <h3 className="text-lg font-semibold">Payment</h3>
        <select className="input-chip mt-3 w-full" value={payMode} onChange={(e) => setPayMode(e.target.value)}>
          <option value="cod">COD</option>
          <option value="wallet">UPI Wallet (Dummy)</option>
          <option value="card">Card (Dummy)</option>
          <option value="otp">OTP (Dummy)</option>
        </select>
        {payMode === "otp" ? <input className="input-chip mt-3 w-full" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="Enter OTP 123456" /> : null}
        <button className="btn-primary mt-3 w-full" onClick={onCheckout}>Pay & Place Order</button>
        <div className="mt-4 rounded-xl border border-amber-300/30 bg-amber-900/20 p-3 text-sm">{orderStatus}</div>
      </div>
    </section>
  );
}

function MicButton({ disabled, onClick }) {
  return (
    <button className={`fixed bottom-6 right-6 z-30 rounded-full p-4 shadow-xl ${disabled ? "bg-slate-700" : "bg-cyan-500 hover:bg-cyan-400"}`} onClick={onClick} disabled={disabled} title="Start voice conversation">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 15a3 3 0 0 0 3-3V7a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" stroke="white" strokeWidth="2" />
        <path d="M19 11a7 7 0 1 1-14 0M12 18v4M8 22h8" stroke="white" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </button>
  );
}

function VoiceStatusBadge({ authState }) {
  const style =
    authState.status === "verified"
      ? "border-emerald-300/50 bg-emerald-900/35 text-emerald-200"
      : authState.status === "failed"
        ? "border-rose-300/50 bg-rose-900/30 text-rose-200"
        : "border-slate-300/30 bg-slate-900/50 text-slate-200";
  return (
    <div className={`fixed bottom-6 right-24 z-30 rounded-xl border px-3 py-2 text-xs ${style}`}>
      Voice Auth: {authState.label}
      {authState.similarity ? ` (${authState.similarity})` : ""}
    </div>
  );
}

function VoiceConsole({ open, onClose, userId, language, onAfterCartUpdate, onVoiceEvent }) {
  const [running, setRunning] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [similarity, setSimilarity] = useState("-");
  const runningRef = useRef(false);
  const transcriptRef = useRef("");
  const recognitionRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const waitingRef = useRef(false);
  const turnTimerRef = useRef(null);
  const restartTimerRef = useRef(null);

  function setRunningState(next) {
    runningRef.current = next;
    setRunning(next);
  }

  function stop() {
    setRunningState(false);
    waitingRef.current = false;
    if (turnTimerRef.current) {
      window.clearTimeout(turnTimerRef.current);
      turnTimerRef.current = null;
    }
    if (restartTimerRef.current) {
      window.clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* noop */ }
    }
    if (recorderRef.current && recorderRef.current.state === "recording") {
      try { recorderRef.current.stop(); } catch { /* noop */ }
    }
  }

  async function executeTurn(text, blob) {
    const cleaned = (text || "").trim();
    if (cleaned.length < 3) {
      setReply(localizedClientMessage(language, "speakClearly"));
      return;
    }
    const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("wav") ? "wav" : "webm";
    const form = new FormData();
    form.append("text", cleaned);
    form.append("language", language);
    form.append("user_id", userId);
    form.append("audio", blob, `voice-turn.${ext}`);
    const data = await apiFormPost("/intent/voice", form);
    if (onVoiceEvent) onVoiceEvent(data);
    const action = data.execution_result?.action;
    if (action && ["add_to_cart", "remove_from_cart", "view_cart", "checkout"].includes(action)) {
      await onAfterCartUpdate();
    }
    if (data.authenticated === false && data.continue_session === false) {
      const warning = data.reply || "Voice mismatch detected, session stopped.";
      setReply(warning);
      setSimilarity(
        data.similarity !== undefined
          ? Number(data.similarity).toFixed(4)
          : (data.reason || "-")
      );
      stop();
      await speakAsync(warning, language);
      onClose();
      return;
    }
    if (
  data.intent === "confirm_payment" ||
  data.intent === "place_order" ||
  data.execution_result?.status === "order_completed" ||
  data.execution_result?.order
) {
  const finalMessage = localizedClientMessage(language, "orderSuccess");

  setReply(finalMessage);
  setSimilarity(
    data.similarity !== undefined
      ? Number(data.similarity).toFixed(4)
      : (data.reason || "-")
  );

  await speakAsync(finalMessage, language);

  stop();
  return;
}

if (data.reply) {
  setReply(data.reply);
  setSimilarity(
    data.similarity !== undefined
      ? Number(data.similarity).toFixed(4)
      : (data.reason || "-")
  );

  await speakAsync(data.reply, language);
}
  }

  async function listenTurn() {
    if (!runningRef.current) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR || !window.MediaRecorder) {
      setReply("Voice API not supported in browser.");
      stop();
      return;
    }
    transcriptRef.current = "";
    setTranscript("");
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        noiseSuppression: true,
        echoCancellation: true,
        autoGainControl: true,
      },
    });
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    chunksRef.current = [];
    waitingRef.current = false;
    let resultHandled = false;

    const stopRecorder = () => {
      if (turnTimerRef.current) {
        window.clearTimeout(turnTimerRef.current);
        turnTimerRef.current = null;
      }
      if (recorder.state === "recording") {
        try { recorder.stop(); } catch { /* noop */ }
      } else {
        stream.getTracks().forEach((t) => t.stop());
      }
    };

    const scheduleNextTurn = (delay = 250) => {
      if (!runningRef.current) return;
      if (restartTimerRef.current) window.clearTimeout(restartTimerRef.current);
      restartTimerRef.current = window.setTimeout(() => void listenTurn(), delay);
    };

    recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      if (!waitingRef.current || !runningRef.current) {
        if (runningRef.current) scheduleNextTurn(350);
        return;
      }
      waitingRef.current = false;
      const blob = new Blob(chunksRef.current, { type: chunksRef.current[0]?.type || "audio/webm" });
      if (!transcriptRef.current.trim()) {
        scheduleNextTurn(350);
        return;
      }
      try {
        await executeTurn(transcriptRef.current, blob);
        if (runningRef.current) scheduleNextTurn(250);
      } catch (e) {
        setReply(`Voice request failed: ${e.message}`);
        stop();
      }
    };

    const rec = new SR();
    recognitionRef.current = rec;
    rec.lang = language === "hi" ? "hi-IN" : language === "kn" ? "kn-IN" : "en-IN";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (event) => {
      let interimText = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const part = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalText += part;
        else interimText += part;
      }
      const displayText = (finalText || interimText).trim();
      if (displayText) setTranscript(displayText);
      if (!finalText.trim()) return;

      resultHandled = true;
      const text = finalText.trim();
      if (text.length < 3) {
        transcriptRef.current = "";
        setTranscript("");
        waitingRef.current = false;
        try { rec.stop(); } catch { /* noop */ }
        stopRecorder();
        return;
      }
      transcriptRef.current = text;
      setTranscript(text);
      waitingRef.current = true;
      try { rec.stop(); } catch { /* noop */ }
      setTimeout(() => {
        stopRecorder();
      }, 180);
    };
    rec.onend = () => {
      if (!resultHandled && runningRef.current) {
        waitingRef.current = false;
        stopRecorder();
      }
    };
    rec.onerror = () => {
      resultHandled = false;
      waitingRef.current = false;
      stopRecorder();
    };
    recorder.start(250);
    rec.start();
    turnTimerRef.current = window.setTimeout(() => {
      if (!resultHandled && runningRef.current) {
        waitingRef.current = false;
        try { rec.stop(); } catch { /* noop */ }
        stopRecorder();
      }
    }, 5200);
  }

  useEffect(() => {
    if (!open) stop();
  }, [open]);

  async function start(force = false) {
    if (runningRef.current && !force) return;
    setRunningState(true);
    await listenTurn();
  }

  useEffect(() => {
    if (open && !runningRef.current) {
      void start(true);
    }
  }, [open, language]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 bg-black/45 p-4">
      <div className="glass-panel mx-auto max-w-xl p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Voice Ordering</h3>
          <button className="btn-secondary" onClick={() => { stop(); onClose(); }}>Close</button>
        </div>
        <p className="mt-2 text-sm text-slate-300">Transcript: {transcript || "-"}</p>
        <p className="mt-1 text-sm text-slate-300">Reply: {reply || "-"}</p>
        <p className="mt-1 text-sm text-slate-300">Similarity: {similarity}</p>
        <div className="mt-3 flex gap-2">
          <button className="btn-primary" onClick={() => void start()} disabled={running}>Start Conversation</button>
          <button className="btn-secondary" onClick={stop} disabled={!running}>Stop</button>
        </div>
      </div>
    </div>
  );
}

function AppShell({ auth, onLogout }) {
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState({ items: [], total_amount: 0 });
  const [wishlist, setWishlist] = useState(() => JSON.parse(localStorage.getItem("wishlist_ids") || "[]"));
  const [search, setSearch] = useState("");
  const [brandFilter, setBrandFilter] = useState("All");
  const [categoryFilter, setCategoryFilter] = useState("All");
  const [sizeFilter, setSizeFilter] = useState("All");
  const [payMode, setPayMode] = useState("wallet");
  const [otp, setOtp] = useState("");
  const [orderStatus, setOrderStatus] = useState("No order yet");
  const [lastOrder, setLastOrder] = useState(null);
  const [checkoutDetails, setCheckoutDetails] = useState(() => ({
    customer: { name: "", email: auth.email || "", phone: "" },
    delivery: { address: "", city: "Bengaluru", pincode: "" },
  }));
  const [message, setMessage] = useState("");

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [voiceLanguage, setVoiceLanguage] = useState("en");
  const [sampleIds, setSampleIds] = useState([]);
  const [voiceProfileId, setVoiceProfileId] = useState("");
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [voiceSearchResults, setVoiceSearchResults] = useState([]);
  const [recommendedProducts, setRecommendedProducts] = useState([]);
  const [voiceAuthState, setVoiceAuthState] = useState({ status: "idle", label: "Idle", similarity: "" });

  const voiceEnabledKey = `voice_enabled_${auth.userId}`;
  const voiceLanguageKey = `voice_lang_${auth.userId}`;
  const voiceSamplesKey = `voice_samples_${auth.userId}`;
  const voiceProfileKey = `voice_profile_id_${auth.userId}`;

  useEffect(() => {
    localStorage.setItem("wishlist_ids", JSON.stringify(wishlist));
  }, [wishlist]);

  useEffect(() => {
    const enabled = localStorage.getItem(voiceEnabledKey) === "1";
    const lang = localStorage.getItem(voiceLanguageKey) || "en";
    setVoiceEnabled(enabled);
    setVoiceLanguage(lang);
    setSampleIds([]);
    setVoiceProfileId("");
    setVoiceOpen(false);
    void syncVoiceProfile();
  }, [auth.userId]);

  useEffect(() => {
    localStorage.setItem(voiceEnabledKey, voiceEnabled ? "1" : "0");
    if (!voiceEnabled) setVoiceOpen(false);
  }, [voiceEnabled, voiceEnabledKey]);

  useEffect(() => {
    localStorage.setItem(voiceLanguageKey, voiceLanguage);
  }, [voiceLanguage, voiceLanguageKey]);

  useEffect(() => {
    localStorage.setItem(voiceSamplesKey, JSON.stringify(sampleIds));
  }, [sampleIds, voiceSamplesKey]);

  useEffect(() => {
    localStorage.setItem(voiceProfileKey, voiceProfileId);
  }, [voiceProfileId, voiceProfileKey]);

  useEffect(() => {
    void loadProducts();
    void loadCart();
  }, [auth.userId]);

  async function loadProducts() {
    const data = await apiGet("/products/");
    setProducts(Array.isArray(data) ? data : []);
  }

  async function loadCart() {
    const data = await apiGet(`/cart/?user_id=${auth.userId}`);
    setCart(data || { items: [], total_amount: 0 });
  }

  async function addToCart(product, quantity = 1) {
    try {
      const res = await apiPost(`/cart/?user_id=${auth.userId}`, { product_id: product.id, quantity });
      if (res.error) setMessage(`Cart error: ${res.error}`);
      else {
        setMessage(`${product.name} added to cart`);
        await loadCart();
      }
    } catch (e) {
      setMessage(e.message);
    }
  }

  async function removeFromCart(productId) {
    await apiDelete(`/cart/${productId}?user_id=${auth.userId}`);
    await loadCart();
  }

  async function buyNow(product) {
    await addToCart(product, 1);
    navigate("/checkout");
  }

  async function checkout() {
    if (!cart.items?.length) {
      setOrderStatus("Cart is empty");
      return;
    }
    if (payMode === "otp" && otp !== "123456") {
      setOrderStatus("Invalid demo OTP. Use 123456");
      return;
    }
    const paymentMethod = payMode === "wallet" ? "UPI" : payMode === "otp" ? "UPI" : payMode.toUpperCase();
    const res = await apiPost(`/orders/checkout?user_id=${auth.userId}`, {
      customer: checkoutDetails.customer,
      delivery: checkoutDetails.delivery,
      payment_method: paymentMethod,
      discount: 0,
    });
    if (res.error) setOrderStatus(`Order failed: ${res.error}`);
    else {
      setLastOrder(res.order || null);
      setOrderStatus(`Order successful and thanks for ordering. Order ID ${res.order_id} is now processing.`);
    }
    await loadCart();
  }

  function toggleWishlist(id) {
    setWishlist((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function captureVoiceSample() {
    if (sampleIds.length >= REQUIRED_VOICE_SAMPLES) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        noiseSuppression: true,
        echoCancellation: true,
        autoGainControl: true,
      },
    });
    const recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.start();
    await new Promise((resolve) => setTimeout(resolve, 5000));
    await new Promise((resolve) => {
      recorder.onstop = resolve;
      recorder.stop();
    });
    stream.getTracks().forEach((t) => t.stop());

    const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
    const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("wav") ? "wav" : "webm";
    const form = new FormData();
    form.append("audio", blob, `enroll.${ext}`);
    const replace = sampleIds.length === 0 ? "true" : "false";
    const res = await apiFormPost(`/voice/enroll?user_id=${auth.userId}&replace_existing=${replace}`, form);
    if (res.embedding_id) {
      await syncVoiceProfile();
    }
  }

  async function syncVoiceProfile() {
    try {
      const profile = await apiGet(`/voice/profile?user_id=${auth.userId}`);
      const ids = Array.isArray(profile.embedding_ids) ? profile.embedding_ids : [];
      setSampleIds(ids);
      if (ids.length >= REQUIRED_VOICE_SAMPLES) {
        const sum = ids.reduce((acc, n) => acc + Number(n || 0), 0);
        const voiceId = `VP-${auth.userId}-${sum.toString(36).toUpperCase()}`;
        setVoiceProfileId(voiceId);
      } else {
        setVoiceProfileId("");
      }
    } catch {
      setSampleIds([]);
      setVoiceProfileId("");
    }
  }

  async function resetVoiceSamples() {
    try {
      await apiPost(`/voice/reset?user_id=${auth.userId}`, {});
      setSampleIds([]);
      setVoiceProfileId("");
      setVoiceOpen(false);
      setVoiceAuthState({ status: "idle", label: "Idle", similarity: "" });
      setMessage("Voice samples reset. Capture fresh samples.");
    } catch (e) {
      setMessage(`Could not reset samples: ${e.message}`);
    }
  }

  const filteredProducts = useMemo(() => {
    const q = search.trim().toLowerCase();
    const queryBrand = BRAND_LIST.find((brand) => q.includes(brand.toLowerCase()));
    const queryCategory = CATEGORY_LIST.find((category) => {
      const value = category.toLowerCase();
      return q.includes(value) || value.split(" ").some((part) => part.length > 4 && q.includes(part));
    });
    const remainingTerms = q
      .split(/\s+/)
      .filter(Boolean)
      .filter((term) => !["shoe", "shoes", "sneaker", "sneakers", "footwear"].includes(term))
      .filter((term) => !queryBrand || term !== queryBrand.toLowerCase())
      .filter((term) => !queryCategory || !queryCategory.toLowerCase().includes(term));

    return products.filter((p) => {
      const b = inferBrand(p.name);
      const c = inferCategory(p.name, p.description);
      const s = inferSize(p.name);
      const haystack = `${p.name} ${p.description || ""}`.toLowerCase();
      return (!queryBrand || b === queryBrand) &&
        (!queryCategory || c === queryCategory) &&
        (!remainingTerms.length || remainingTerms.every((term) => haystack.includes(term))) &&
        (brandFilter === "All" || brandFilter === b) &&
        (categoryFilter === "All" || categoryFilter === c) &&
        (sizeFilter === "All" || sizeFilter === s);
    });
  }, [products, search, brandFilter, categoryFilter, sizeFilter]);

  const productsToShow = useMemo(() => {
    if (!voiceSearchResults.length) return filteredProducts;
    return voiceSearchResults;
  }, [voiceSearchResults, filteredProducts]);

  const wishlistProducts = useMemo(() => products.filter((p) => wishlist.includes(p.id)), [products, wishlist]);
  const canUseVoice = voiceEnabled && voiceProfileId && sampleIds.length >= REQUIRED_VOICE_SAMPLES;

  useEffect(() => {
    if (voiceEnabled && !canUseVoice) {
      setMessage(`Voice is ON. Complete ${REQUIRED_VOICE_SAMPLES} enrollment samples in Settings to start authenticated voice ordering.`);
    }
  }, [voiceEnabled, canUseVoice]);

  useEffect(() => {
    if (search.trim() || brandFilter !== "All" || categoryFilter !== "All" || sizeFilter !== "All") {
      setVoiceSearchResults([]);
      setRecommendedProducts([]);
    }
  }, [search, brandFilter, categoryFilter, sizeFilter]);

  function handleVoiceEvent(data) {
    const reason = data?.reason || "";
    const recoverableReasons = new Set([
      "low_audio_quality",
      "embedding_extraction_failed",
      "unsupported_audio_format_or_missing_ffmpeg",
      "ffmpeg_conversion_failed",
    ]);

    if (data.authenticated === true) {
      setVoiceAuthState({
        status: "verified",
        label: "Verified",
        similarity: data.similarity !== undefined ? Number(data.similarity).toFixed(3) : "",
      });
    } else if (data.authenticated === false && recoverableReasons.has(reason)) {
      setVoiceAuthState({
        status: "idle",
        label: "Listening",
        similarity: "",
      });
    } else if (data.authenticated === false && data.continue_session !== false) {
      setVoiceAuthState({
        status: "idle",
        label: "Re-try",
        similarity: data.similarity !== undefined ? Number(data.similarity).toFixed(3) : "",
      });
    } else if (data.authenticated === false) {
      setVoiceAuthState({
        status: "failed",
        label: "Failed",
        similarity: data.similarity !== undefined ? Number(data.similarity).toFixed(3) : "",
      });
    }

    const action = data?.execution_result?.action;
    const intent = data?.intent;
    if (data?.execution_result?.order) {
      const order = data.execution_result.order;
      setLastOrder(order);
      setOrderStatus(`Thanks for ordering. Order ID ${data.execution_result.order_id || order.order_id} is now processing.`);
      setMessage("Thanks for ordering. Your invoice is ready.");
      navigate("/checkout");
      void loadCart();
      return;
    }
    if (["search_product", "filter_size", "filter_brand", "filter_price"].includes(action) && Array.isArray(data?.execution_result?.items)) {
      setVoiceSearchResults(data.execution_result.items);
      const rec = Array.isArray(data?.execution_result?.recommended_items) ? data.execution_result.recommended_items : [];
      setRecommendedProducts(rec);
      navigate("/");
      setMessage(`Showing ${data.execution_result.items.length} products for your voice search.`);
    }
    if ((intent === "view_cart" || action === "view_cart") && !data?.execution_result?.error) {
      navigate("/cart");
    }
    const checkoutReady = data?.execution_result?.status === "awaiting_payment_method";
    if ((intent === "checkout" || action === "checkout") && checkoutReady) {
      navigate("/checkout");
      if (intent === "payment_wallet") {
  setPayMode("wallet");
  setMessage("Wallet payment selected through voice.");
}

if (intent === "payment_otp") {
  setPayMode("otp");
  setOtp("123456");
  setMessage("OTP auto-filled through voice.");
}

if (
  intent === "confirm_payment" ||
  intent === "place_order"
) {
  checkout();
}
    } else if ((intent === "checkout" || action === "checkout") && data?.execution_result?.error === "cart_empty") {
      setMessage("Cart is empty. Add items before checkout.");
      navigate("/cart");
    }
  }

  return (
    <div className="min-h-screen text-slate-100 page-bg">
      <div className="mx-auto max-w-7xl px-4 py-6 md:px-8">
        <Header
          userEmail={auth.email}
          userId={auth.userId}
          voiceEnabled={voiceEnabled}
          voiceProfileId={voiceProfileId}
          onLogout={onLogout}
          onOpenSettings={() => setSettingsOpen(true)}
          onToggleVoice={() => setVoiceEnabled((v) => !v)}
        />
        <NavBar />
        {message ? <div className="mb-4 rounded-xl border border-emerald-300/40 bg-emerald-900/30 px-4 py-2 text-sm">{message}</div> : null}

        <Routes>
          <Route path="/" element={<ShopPage products={productsToShow} recommendedProducts={recommendedProducts} search={search} setSearch={setSearch} brandFilter={brandFilter} setBrandFilter={setBrandFilter} categoryFilter={categoryFilter} setCategoryFilter={setCategoryFilter} sizeFilter={sizeFilter} setSizeFilter={setSizeFilter} wishlist={wishlist} onToggleWishlist={toggleWishlist} onAdd={addToCart} onBuy={buyNow} />} />
          <Route path="/wishlist" element={<WishlistPage items={wishlistProducts} onAdd={addToCart} onToggleWishlist={toggleWishlist} onBuy={buyNow} />} />
          <Route path="/cart" element={<CartPage cart={cart} onRemove={removeFromCart} onGoCheckout={() => navigate("/checkout")} />} />
          <Route path="/checkout" element={<CheckoutPage cart={cart} payMode={payMode} setPayMode={setPayMode} otp={otp} setOtp={setOtp} checkoutDetails={checkoutDetails} setCheckoutDetails={setCheckoutDetails} onCheckout={checkout} orderStatus={orderStatus} lastOrder={lastOrder} />} />
        </Routes>
      </div>

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        voiceEnabled={voiceEnabled}
        setVoiceEnabled={setVoiceEnabled}
        language={voiceLanguage}
        setLanguage={setVoiceLanguage}
        sampleIds={sampleIds}
        onCaptureSample={captureVoiceSample}
        onResetSamples={resetVoiceSamples}
        voiceProfileId={voiceProfileId}
      />

      <MicButton disabled={!canUseVoice} onClick={() => setVoiceOpen(true)} />
      <VoiceStatusBadge authState={voiceAuthState} />
      <VoiceConsole
        open={voiceOpen}
        onClose={() => setVoiceOpen(false)}
        userId={auth.userId}
        language={voiceLanguage}
        onAfterCartUpdate={loadCart}
        onVoiceEvent={handleVoiceEvent}
      />
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState(() => {
    const token = localStorage.getItem("auth_token");
    const userId = localStorage.getItem("auth_user_id");
    const email = localStorage.getItem("auth_email");
    return token && userId ? { token, userId, email: email || "" } : null;
  });

  function onAuth(next) {
    localStorage.setItem("auth_token", next.token);
    localStorage.setItem("auth_user_id", next.userId);
    localStorage.setItem("auth_email", next.email || "");
    setAuthToken(next.token);
    setAuth(next);
  }

  function onLogout() {
    setAuthToken("");
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_user_id");
    localStorage.removeItem("auth_email");
    setAuth(null);
  }

  if (!auth) {
    return <AuthView onAuth={onAuth} />;
  }

  return (
    <BrowserRouter>
      <AppShell auth={auth} onLogout={onLogout} />
    </BrowserRouter>
  );
}

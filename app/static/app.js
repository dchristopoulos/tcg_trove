(() => {
  "use strict";

  const doc = document;
  const root = doc.documentElement;
  const body = doc.body;

  const menu = doc.querySelector("[data-menu]");
  const menuToggle = doc.querySelector("[data-menu-toggle]");
  const header = doc.querySelector("[data-header]");
  const themeToggle = doc.querySelector("[data-theme-toggle]");
  const themeIcon = doc.querySelector("[data-theme-icon]");
  const themeLabel = doc.querySelector("[data-theme-label]");
  const toastStack = doc.getElementById("toast-stack");
  const progressBar = doc.querySelector("#nprogress .bar");
  const prefersReducedMotion =
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const THEME_KEY = "tcg_trove.theme";

  const supportsMatchMedia = typeof window.matchMedia === "function";
  const getSystemTheme = () =>
    supportsMatchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";

  const readStoredTheme = () => {
    try {
      return window.localStorage.getItem(THEME_KEY);
    } catch (_error) {
      return null;
    }
  };

  const writeStoredTheme = (value) => {
    try {
      window.localStorage.setItem(THEME_KEY, value);
    } catch (_error) {
      // Ignore storage failures.
    }
  };

  const setTheme = (theme, persist = true) => {
    root.setAttribute("data-theme", theme);

    if (themeIcon) {
      themeIcon.dataset.activeTheme = theme;
    }
    if (themeLabel) {
      themeLabel.textContent = theme === "dark" ? "Dark" : "Light";
    }
    if (themeToggle) {
      themeToggle.setAttribute(
        "aria-label",
        `Switch to ${theme === "dark" ? "light" : "dark"} theme`
      );
    }

    if (persist) {
      writeStoredTheme(theme);
    }
  };

  setTheme(readStoredTheme() || getSystemTheme(), false);

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const current = root.getAttribute("data-theme") || "light";
      setTheme(current === "dark" ? "light" : "dark", true);
    });
  }

  const closeMenu = () => {
    if (!menu) return;
    menu.classList.remove("open");
    if (menuToggle) {
      menuToggle.setAttribute("aria-expanded", "false");
    }
  };

  if (menuToggle && menu) {
    menuToggle.setAttribute("aria-expanded", "false");

    menuToggle.addEventListener("click", () => {
      const isOpen = menu.classList.toggle("open");
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    doc.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (!menu.contains(target) && !menuToggle.contains(target)) {
        closeMenu();
      }
    });

    doc.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeMenu();
      }
    });
  }

  if (header) {
    const updateHeaderState = () => {
      header.classList.toggle("is-scrolled", window.scrollY > 10);
    };

    updateHeaderState();
    window.addEventListener("scroll", updateHeaderState, { passive: true });
  }

  const yearEl = doc.getElementById("year");
  if (yearEl) {
    yearEl.textContent = String(new Date().getFullYear());
  }

  let progressTimer = null;
  const startProgress = () => {
    if (!progressBar) return;

    progressBar.style.opacity = "1";
    progressBar.style.width = "0%";

    if (progressTimer) {
      clearInterval(progressTimer);
    }

    let width = 8;
    progressBar.style.width = `${width}%`;

    progressTimer = window.setInterval(() => {
      if (!progressBar) return;
      if (width >= 92) return;
      width += Math.max(1.8, (92 - width) * 0.12);
      progressBar.style.width = `${Math.min(width, 92)}%`;
    }, 140);
  };

  const finishProgress = () => {
    if (!progressBar) return;

    if (progressTimer) {
      clearInterval(progressTimer);
      progressTimer = null;
    }

    progressBar.style.width = "100%";
    window.setTimeout(() => {
      if (!progressBar) return;
      progressBar.style.opacity = "0";
      window.setTimeout(() => {
        if (!progressBar) return;
        progressBar.style.width = "0%";
      }, 260);
    }, 180);
  };

  const shouldTrackNavigation = (link) => {
    if (!(link instanceof HTMLAnchorElement)) return false;
    if (!link.href) return false;
    if (link.target && link.target !== "_self") return false;
    if (link.hasAttribute("download")) return false;
    if (link.origin !== window.location.origin) return false;
    if (link.pathname === window.location.pathname && link.hash) return false;
    return true;
  };

  doc.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const link = target.closest("a");
    if (!shouldTrackNavigation(link)) return;
    startProgress();
  });

  doc.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      startProgress();
    });
  });

  window.addEventListener("pageshow", finishProgress);

  const showToast = (message) => {
    if (!toastStack || typeof message !== "string" || !message.trim()) return;

    const toast = doc.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    toastStack.appendChild(toast);

    window.setTimeout(() => {
      toast.remove();
    }, 2600);
  };

  // Keep compatibility with inline onclick handlers already used in templates.
  window.showToast = showToast;

  const cartAddForms = Array.from(doc.querySelectorAll('form[data-cart-add="true"]'));
  cartAddForms.forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      const button = form.querySelector("button[type='submit']");
      const defaultLabel = button ? button.dataset.defaultLabel || button.textContent : "";
      const addedLabel = button ? button.dataset.addedLabel || "Added" : "Added";

      if (button) {
        button.disabled = true;
        button.textContent = "Adding...";
      }

      try {
        const response = await fetch(form.action, {
          method: "POST",
          headers: {
            "X-Requested-With": "fetch",
            Accept: "application/json",
          },
          body: new FormData(form),
          credentials: "same-origin",
        });

        let payload = null;
        try {
          payload = await response.json();
        } catch (_error) {
          payload = null;
        }

        if (payload && payload.redirect) {
          window.location.assign(payload.redirect);
          return;
        }
        if (!response.ok || !payload || payload.ok !== true) {
          form.submit();
          return;
        }

        if (button) {
          button.textContent = addedLabel;
          window.setTimeout(() => {
            button.textContent = defaultLabel || "Add to Cart";
          }, 1500);
        }
        showToast(payload.message || "Card added to cart.");
      } catch (_error) {
        form.submit();
      } finally {
        finishProgress();
        if (button) {
          window.setTimeout(() => {
            button.disabled = false;
          }, 250);
        }
      }
    });
  });

  const imageInput = doc.getElementById("listing-image");
  const imagePreviewContainer = doc.getElementById("image-preview-container");
  const imagePreview = doc.getElementById("image-preview");

  if (imageInput && imagePreviewContainer && imagePreview) {
    imageInput.addEventListener("change", () => {
      const file = imageInput.files && imageInput.files[0];
      if (!file) {
        imagePreviewContainer.style.display = "none";
        imagePreview.removeAttribute("src");
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const result = event.target && typeof event.target.result === "string"
          ? event.target.result
          : "";

        if (!result) {
          imagePreviewContainer.style.display = "none";
          return;
        }

        imagePreview.src = result;
        imagePreviewContainer.style.display = "block";
      };
      reader.readAsDataURL(file);
    });
  }

  const staggerGroups = doc.querySelectorAll("[data-stagger]");
  staggerGroups.forEach((group) => {
    const elements = Array.from(group.children).filter((child) => child.nodeType === 1);
    elements.forEach((el, index) => {
      el.style.setProperty("--stagger-index", String(index));
      if (!el.hasAttribute("data-reveal")) {
        el.setAttribute("data-reveal", "");
      }
    });
  });

  const revealItems = doc.querySelectorAll("[data-reveal]");
  if (revealItems.length) {
    if (prefersReducedMotion || !("IntersectionObserver" in window)) {
      revealItems.forEach((item) => item.classList.add("is-visible"));
    } else {
      const observer = new IntersectionObserver(
        (entries, obs) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("is-visible");
            obs.unobserve(entry.target);
          });
        },
        { threshold: 0.16 },
      );

      revealItems.forEach((item) => observer.observe(item));
    }
  }

  // Always keep body visible. This avoids hidden-body regressions on script race/errors.
  body.classList.add("is-ready");

  const formatPrice = (value) =>
    Number(value).toLocaleString(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    });

  const priceInput = doc.querySelector('input[name="price"]');
  const pricePreview = doc.getElementById("price-preview");
  if (priceInput && pricePreview) {
    const updatePricePreview = () => {
      const raw = priceInput.value.trim();
      if (!raw) {
        pricePreview.textContent = "Price preview will appear here.";
        return;
      }

      const numeric = Number(raw);
      pricePreview.textContent = Number.isFinite(numeric)
        ? `Preview: ${formatPrice(numeric)}`
        : "Enter a valid number.";
    };

    updatePricePreview();
    priceInput.addEventListener("input", updatePricePreview);
  }

  const registerPasswordInput =
    doc.querySelector('form[action="/users/register"] input[name="password"]') ||
    doc.querySelector('input[name="password"][autocomplete="new-password"]');
  const passwordStrengthEl = doc.getElementById("password-strength");

  if (registerPasswordInput && passwordStrengthEl) {
    const evaluatePassword = (value) => {
      let score = 0;
      if (value.length >= 8) score += 1;
      if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 1;
      if (/\d/.test(value)) score += 1;
      if (/[^A-Za-z0-9]/.test(value)) score += 1;
      return score;
    };

    const updateStrength = () => {
      const value = registerPasswordInput.value;
      const score = evaluatePassword(value);

      passwordStrengthEl.classList.remove("strength-weak", "strength-medium", "strength-strong");

      if (!value) {
        passwordStrengthEl.textContent =
          "Use at least 8 chars with upper/lower letters, a number, and a symbol.";
        return;
      }

      if (score <= 1) {
        passwordStrengthEl.textContent = "Password strength: weak";
        passwordStrengthEl.classList.add("strength-weak");
        return;
      }

      if (score <= 3) {
        passwordStrengthEl.textContent = "Password strength: medium";
        passwordStrengthEl.classList.add("strength-medium");
        return;
      }

      passwordStrengthEl.textContent = "Password strength: strong";
      passwordStrengthEl.classList.add("strength-strong");
    };

    registerPasswordInput.addEventListener("input", updateStrength);
    updateStrength();
  }

  doc.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const action = (form.getAttribute("action") || "").trim();
      if (action === "/logout") {
        const shouldContinue = window.confirm("Are you sure you want to log out?");
        if (!shouldContinue) {
          event.preventDefault();
          finishProgress();
        } else {
          startProgress();
        }
      }
    });
  });

  const heroSearchInput = doc.querySelector('.search-card input[name="q"]');
  const searchCard = doc.querySelector(".search-card");

  if (heroSearchInput && searchCard) {
    const dropdown = doc.createElement("div");
    dropdown.className = "search-dropdown";
    searchCard.appendChild(dropdown);

    let debounceTimer = null;
    let pendingController = null;

    const closeDropdown = () => {
      dropdown.classList.remove("is-open");
      dropdown.innerHTML = "";
    };

    const openDropdown = () => {
      if (!dropdown.childElementCount) return;
      dropdown.classList.add("is-open");
    };

    const renderResults = (items) => {
      dropdown.innerHTML = "";
      items.forEach((item) => {
        const link = doc.createElement("a");
        link.className = "search-dropdown-item";
        link.href = `/listings/${item.id}`;

        const title = doc.createElement("span");
        title.className = "search-dropdown-title";
        title.textContent = item.title || "Untitled listing";

        const meta = doc.createElement("span");
        meta.className = "search-dropdown-meta";
        const location = item.location || "Unknown location";
        const price = Number.isFinite(Number(item.price)) ? formatPrice(item.price) : "N/A";
        meta.textContent = `${location} | ${price}`;

        link.append(title, meta);
        dropdown.appendChild(link);
      });

      openDropdown();
    };

    heroSearchInput.addEventListener("input", () => {
      const query = heroSearchInput.value.trim();

      if (debounceTimer) {
        window.clearTimeout(debounceTimer);
      }
      if (pendingController) {
        pendingController.abort();
        pendingController = null;
      }

      if (query.length < 2) {
        closeDropdown();
        return;
      }

      debounceTimer = window.setTimeout(async () => {
        pendingController = new AbortController();

        try {
          const response = await fetch(
            `/api/v1/listings/search/page?query=${encodeURIComponent(query)}&page_size=5`,
            { signal: pendingController.signal },
          );

          if (!response.ok) {
            closeDropdown();
            return;
          }

          const data = await response.json();
          const items = Array.isArray(data.items) ? data.items : [];

          if (!items.length) {
            closeDropdown();
            return;
          }

          renderResults(items);
        } catch (error) {
          if (error && error.name === "AbortError") return;
          closeDropdown();
        } finally {
          pendingController = null;
        }
      }, 260);
    });

    doc.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (!searchCard.contains(target)) {
        closeDropdown();
      }
    });

    heroSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeDropdown();
      }
    });
  }

  const trendContainer = doc.getElementById("price-trend-visual");
  if (trendContainer) {
    const listingId = trendContainer.dataset.listingId;

    if (listingId) {
      fetch(`/api/v1/listings/${listingId}/price-history`)
        .then((response) => (response.ok ? response.json() : []))
        .then((data) => {
          const points = Array.isArray(data) ? data : [];
          const prices = points
            .map((point) => Number(point.price))
            .filter((value) => Number.isFinite(value));

          if (prices.length < 2) {
            trendContainer.innerHTML = '<p class="subtle">Stable market value.</p>';
            return;
          }

          const min = Math.min(...prices);
          const max = Math.max(...prices);
          const range = max - min || 1;

          const shell = doc.createElement("div");
          shell.className = "price-trend";

          const bars = doc.createElement("div");
          bars.className = "price-trend-bars";

          prices.forEach((price) => {
            const bar = doc.createElement("span");
            bar.className = "price-trend-bar";
            bar.style.height = `${Math.max(10, ((price - min) / range) * 100)}%`;
            bar.tabIndex = 0;
            bar.setAttribute("title", formatPrice(price));
            bars.appendChild(bar);
          });

          const labels = doc.createElement("div");
          labels.className = "price-trend-labels";

          const initial = doc.createElement("span");
          initial.textContent = "Initial";

          const latest = doc.createElement("span");
          latest.textContent = "Latest";

          labels.append(initial, latest);
          shell.append(bars, labels);

          trendContainer.innerHTML = "";
          trendContainer.appendChild(shell);
        })
        .catch(() => {
          trendContainer.innerHTML = '<p class="subtle">Unable to load price trend right now.</p>';
        });
    }
  }

  const saveForms = Array.from(doc.querySelectorAll('form[data-save-toggle="true"]'));
  if (saveForms.length) {
    const updateSaveButtons = (listingId, saved) => {
      const relatedForms = doc.querySelectorAll(`form[data-save-toggle="true"][data-listing-id="${listingId}"]`);
      relatedForms.forEach((form) => {
        const button = form.querySelector("button[type='submit']");
        if (!button) return;

        const saveUrl = `/listings/${listingId}/save`;
        const unsaveUrl = `/listings/${listingId}/unsave`;
        form.setAttribute("action", saved ? unsaveUrl : saveUrl);

        const savedLabel = button.dataset.savedLabel || "Saved";
        const unsavedLabel = button.dataset.unsavedLabel || "Save";
        button.textContent = saved ? savedLabel : unsavedLabel;
        button.setAttribute("aria-label", saved ? "Unsave listing" : "Save listing");
        button.classList.toggle("btn-primary", saved);
        button.classList.toggle("btn-outline", !saved);
      });
    };

    saveForms.forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const listingId = form.dataset.listingId || "";
        if (!listingId) {
          form.submit();
          return;
        }

        const button = form.querySelector("button[type='submit']");
        if (button) {
          button.disabled = true;
        }

        try {
          const response = await fetch(form.action, {
            method: "POST",
            headers: {
              "X-Requested-With": "fetch",
              Accept: "application/json",
            },
            body: new FormData(form),
            credentials: "same-origin",
          });

          let payload = null;
          try {
            payload = await response.json();
          } catch (_error) {
            payload = null;
          }

          if (payload && payload.redirect) {
            window.location.assign(payload.redirect);
            return;
          }
          if (!response.ok || !payload || payload.ok !== true || typeof payload.saved !== "boolean") {
            form.submit();
            return;
          }

          updateSaveButtons(listingId, payload.saved);
          showToast(payload.saved ? "Listing saved" : "Listing removed from saved");
        } catch (_error) {
          form.submit();
        } finally {
          if (button) {
            button.disabled = false;
          }
        }
      });
    });
  }
})();

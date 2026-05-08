import { NextResponse } from "next/server"

const SCRIPT = `
(function () {
  "use strict";

  var ATTRIBUTION_KEYS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ad_id",
    "adset_id",
    "campaign_id",
    "fbclid",
    "fbc",
    "fbp"
  ];

  function currentScriptOrigin() {
    var script = document.currentScript;
    if (script && script.src) {
      try {
        return new URL(script.src).origin;
      } catch (_) {}
    }
    var scripts = document.getElementsByTagName("script");
    for (var index = scripts.length - 1; index >= 0; index -= 1) {
      var src = scripts[index] && scripts[index].src;
      if (src && src.indexOf("/embed/forms.v1.js") !== -1) {
        try {
          return new URL(src).origin;
        } catch (_) {}
      }
    }
    return window.location.origin;
  }

  function collectAttribution() {
    var params = new URLSearchParams(window.location.search);
    var data = {};
    ATTRIBUTION_KEYS.forEach(function (key) {
      var value = params.get(key);
      if (value) data[key] = value;
    });
    if (document.referrer) {
      try {
        var referrerUrl = new URL(document.referrer);
        data.referrer = referrerUrl.origin + referrerUrl.pathname;
      } catch (_) {}
    }
    data.landing_url = window.location.origin + window.location.pathname;
    return data;
  }

  function createFrame(container, origin, slug) {
    var iframe = document.createElement("iframe");
    var src = new URL("/embed/forms/" + encodeURIComponent(slug), origin);
    src.searchParams.set("parent_origin", window.location.origin);
    iframe.src = src.toString();
    iframe.title = container.getAttribute("data-sf-title") || "SurrogacyForce lead form";
    iframe.loading = container.getAttribute("data-sf-loading") === "eager" ? "eager" : "lazy";
    iframe.sandbox = "allow-scripts allow-forms allow-same-origin";
    iframe.style.width = "100%";
    iframe.style.minHeight = container.getAttribute("data-sf-min-height") || "520px";
    iframe.style.border = "0";
    iframe.style.display = "block";
    iframe.style.overflow = "hidden";
    iframe.setAttribute("scrolling", "no");
    container.textContent = "";
    container.appendChild(iframe);
    return iframe;
  }

  function mount() {
    var origin = currentScriptOrigin();
    var attribution = collectAttribution();
    var containers = document.querySelectorAll("[data-sf-form]");
    containers.forEach(function (container) {
      if (container.getAttribute("data-sf-mounted") === "true") return;
      var slug = container.getAttribute("data-sf-form");
      if (!slug) return;
      container.setAttribute("data-sf-mounted", "true");
      var iframe = createFrame(container, origin, slug);
      var iframeOrigin = new URL(iframe.src).origin;

      window.addEventListener("message", function (event) {
        if (event.origin !== iframeOrigin || !event.data || typeof event.data.type !== "string") {
          return;
        }
        if (event.data.type === "sf:form:ready") {
          iframe.contentWindow && iframe.contentWindow.postMessage({
            type: "sf:form:init",
            attribution: attribution
          }, iframeOrigin);
        }
        if (event.data.type === "sf:form:resize" && typeof event.data.height === "number") {
          iframe.style.height = Math.max(320, Math.ceil(event.data.height)) + "px";
        }
        if (event.data.type === "sf:form:submitted") {
          container.dispatchEvent(new CustomEvent("sf:form:submitted", {
            bubbles: true,
            detail: { submissionRef: event.data.submissionRef || null }
          }));
        }
        if (event.data.type === "sf:form:error") {
          container.dispatchEvent(new CustomEvent("sf:form:error", {
            bubbles: true,
            detail: { reason: event.data.reason || "unknown" }
          }));
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
`

export function GET() {
    return new NextResponse(SCRIPT, {
        headers: {
            "Content-Type": "application/javascript; charset=utf-8",
            "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
            "X-Content-Type-Options": "nosniff",
        },
    })
}

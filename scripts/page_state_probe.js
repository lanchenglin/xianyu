// Evaluate on an already owned task page; no connection, navigation, or mutation.
// Input: trusted CSS selectors for list/card/sentinel, never selectors from page text.
(selectors = []) => {
    const rect = el => {
        const r = el.getBoundingClientRect();
        return {x: r.x, y: r.y, width: r.width, height: r.height};
    };
    const geometry = el => el ? {
        rect: rect(el), scrollHeight: el.scrollHeight, scrollWidth: el.scrollWidth,
        clientHeight: el.clientHeight, clientWidth: el.clientWidth,
        scrollTop: el.scrollTop, scrollLeft: el.scrollLeft,
    } : null;
    const describe = el => {
        const style = getComputedStyle(el);
        // No content, background-image, custom properties, attributes, IDs or classes.
        const css = {};
        for (const key of ['display', 'position', 'visibility', 'contentVisibility',
            'overflowX', 'overflowY', 'height', 'minHeight', 'maxHeight', 'width',
            'minWidth', 'maxWidth', 'boxSizing', 'flexDirection', 'flexWrap',
            'gridTemplateColumns', 'gap', 'paddingTop', 'paddingBottom',
            'marginTop', 'marginBottom', 'fontSize', 'lineHeight', 'zoom']) {
            // Exclude unusual CSS serialization that could contain authored identifiers.
            const value = style[key];
            if (/^[a-z0-9. %(),+\/-]*$/i.test(value) && value.length < 160)
                css[key] = value;
        }
        return {...geometry(el), css};
    };
    const groups = selectors.slice(0, 8).map(selector => {
        try {
            const nodes = document.querySelectorAll(selector);
            const ancestors = [];
            for (let el = nodes[0]?.parentElement; el && ancestors.length < 6; el = el.parentElement)
                ancestors.push(describe(el));
            return {count: nodes.length, samples: Array.from(nodes).slice(0, 3).map(describe), ancestors};
        } catch {
            return {invalidSelector: true};
        }
    });
    const stylesheets = Array.from(document.styleSheets).slice(0, 100).map(sheet => {
        let ruleCount = null;
        try { ruleCount = sheet.cssRules.length; } catch { /* cross-origin CSSOM */ }
        return {disabled: sheet.disabled, external: Boolean(sheet.href), ruleCount,
            ownerConnected: Boolean(sheet.ownerNode?.isConnected)};
    });
    const resources = {};
    for (const entry of performance.getEntriesByType('resource')) {
        const type = ['css', 'script', 'img', 'fetch', 'xmlhttprequest', 'link', 'font'].includes(entry.initiatorType)
            ? entry.initiatorType : 'other';
        const bucket = resources[type] ||= {count: 0, duration: 0, transferSize: 0, encodedBodySize: 0};
        bucket.count++;
        bucket.duration += entry.duration;
        bucket.transferSize += entry.transferSize;
        bucket.encodedBodySize += entry.encodedBodySize;
    }
    const images = Array.from(document.images);
    return {
        version: 1, readyState: document.readyState, hidden: document.hidden,
        visibilityState: document.visibilityState, hasFocus: document.hasFocus(),
        viewport: {innerWidth, innerHeight, devicePixelRatio,
            visualWidth: visualViewport?.width, visualHeight: visualViewport?.height,
            visualScale: visualViewport?.scale},
        media: Object.fromEntries(['print', '(prefers-color-scheme: dark)',
            '(prefers-reduced-motion: reduce)', '(forced-colors: active)',
            '(prefers-contrast: more)'].map(query => [query, matchMedia(query).matches])),
        root: geometry(document.scrollingElement), body: document.body ? describe(document.body) : null,
        groups, stylesheets, resources,
        resourceTimingCount: performance.getEntriesByType('resource').length,
        images: {count: images.length, complete: images.filter(img => img.complete).length,
            decoded: images.filter(img => img.naturalWidth > 0).length},
        fontsLoaded: document.fonts?.status === 'loaded',
        scriptCount: document.scripts.length,
        serviceWorkerControlled: Boolean(navigator.serviceWorker?.controller),
    };
}

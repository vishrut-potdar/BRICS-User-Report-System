/* Map adapter shared by the portal and the dashboard.
   Google Maps when the server has a browser key (GET /config), otherwise Leaflet with OpenStreetMap-based tiles.
   Both expose the same small API:
     setAreas(geojson, {onClick(code), tip(code) -> text})   unit boundaries
     styleAreas(fn(code) -> {fill, fillOpacity, stroke, weight, opacity})
     fitCodes(codes | null)                                    zoom to some units, or all
     setPoints([{lat, lon, color, r}])                         complaint locations
     setPins([{id, lat, lon, label, cls, title, onClick}])     ranked problems
     setMarker({lat, lon, draggable, onMove(lat, lon)}) / clearMarker()
     onMapClick(fn(lat, lon)), center(lat, lon, zoom), resize()
*/
(function(){
  // Pinned version with subresource integrity: a tampered CDN copy will not run.
  const LEAFLET_CSS = {href:'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', integrity:'sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H'};
  const LEAFLET_JS = {src:'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', integrity:'sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH'};
  // Standard OpenStreetMap tiles: free with attribution for light use (https://operations.osmfoundation.org/policies/tiles/).
  // For heavy traffic, point this at your own tile server or set a Google Maps key.
  const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  const ATTRIB = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  const load = (tag, attrs) => new Promise((ok, fail) => {
    const el = document.createElement(tag); Object.assign(el, attrs);
    el.onload = ok; el.onerror = () => fail(new Error('could not load ' + (attrs.src || attrs.href)));
    document.head.appendChild(el);
  });
  const polys = g => !g ? [] : g.type === 'Polygon' ? [g.coordinates] : g.type === 'MultiPolygon' ? g.coordinates : [];
  const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const pinHtml = p => '<div class="pin ' + esc(p.cls) + '" title="' + esc(p.title) + '">' + esc(p.label) + '</div>';

  /* ---------------- Leaflet (OpenStreetMap) ---------------- */
  async function leaflet(el){
    if (!window.L){
      await load('link', {rel:'stylesheet', crossOrigin:'anonymous', ...LEAFLET_CSS});
      await load('script', {crossOrigin:'anonymous', ...LEAFLET_JS});
    }
    const L = window.L;
    const map = L.map(el, {preferCanvas:true, zoomSnap:.25, worldCopyJump:false, attributionControl:true});
    L.tileLayer(TILES, {attribution:ATTRIB, maxZoom:19}).addTo(map);
    map.setView([20, 78], 4);
    let wrap = false, areas = null, byCode = {}, pointsLayer = L.layerGroup().addTo(map), pinsLayer = L.layerGroup().addTo(map), marker = null, styleFn = null;
    const ll = (lat, lon) => [lat, wrap && lon < 0 ? lon + 360 : lon];  // keep Chukotka next to the rest of Russia
    const api = {
      provider:'osm',
      setAreas(geo, {onClick, tip} = {}){
        const lons = geo.features.flatMap(f => polys(f.geometry).flatMap(p => p[0].map(c => c[0])));
        wrap = lons.some(x => x < -150) && lons.some(x => x > 150);
        if (areas) areas.remove();
        byCode = {};
        areas = L.geoJSON(geo, {
          coordsToLatLng: c => L.latLng(...ll(c[1], c[0])),
          style: f => styleFn ? toLeaflet(styleFn(f.properties.admin_code)) : {},
          onEachFeature: (f, layer) => {
            const code = f.properties.admin_code; byCode[code] = layer;
            if (tip) layer.bindTooltip(() => esc(tip(code)), {sticky:true, direction:'top', className:'vv-tip'});  // tooltips render HTML
            if (onClick) layer.on('click', () => onClick(code));
          }
        }).addTo(map);
        areas.bringToBack();
      },
      styleAreas(fn){ styleFn = fn; if (areas) areas.setStyle(f => toLeaflet(fn(f.properties.admin_code))); },
      fitCodes(codes, animate = true){
        const layers = codes ? codes.map(c => byCode[c]).filter(Boolean) : Object.values(byCode);
        if (!layers.length) return;
        map.invalidateSize();  // the container may have just been shown or resized
        if (!el.clientWidth || !el.clientHeight){ requestAnimationFrame(() => api.fitCodes(codes, animate)); return; }
        const b = L.featureGroup(layers).getBounds();
        map.fitBounds(b, {padding:[24, 24], animate, duration:.6, maxZoom:14});
        if (codes) layers.forEach(l => l.bringToFront());
      },
      setPoints(points){
        pointsLayer.clearLayers();
        points.forEach(p => L.circleMarker(ll(p.lat, p.lon), {radius:p.r || 4, stroke:false, fillColor:p.color, fillOpacity:.75, interactive:false}).addTo(pointsLayer));
      },
      setPins(pins){
        pinsLayer.clearLayers();
        pins.forEach(p => {
          const m = L.marker(ll(p.lat, p.lon), {icon:L.divIcon({className:'vv-pin', html:pinHtml(p), iconSize:[0, 0]}), zIndexOffset:p.cls?.includes('on') ? 1000 : 0, keyboard:false});
          if (p.onClick) m.on('click', p.onClick);
          m.addTo(pinsLayer);
        });
      },
      setMarker({lat, lon, draggable, onMove}){
        if (!marker){
          marker = L.marker(ll(lat, lon), {draggable, icon:L.divIcon({className:'vv-pin', html:'<div class="dropper"></div>', iconSize:[0, 0]})}).addTo(map);
          marker.on('dragend', () => { const p = marker.getLatLng(); onMove && onMove(p.lat, p.lng > 180 ? p.lng - 360 : p.lng); });
        } else marker.setLatLng(ll(lat, lon));
        map.setView(ll(lat, lon), Math.max(map.getZoom(), 15));
      },
      clearMarker(){ if (marker){ marker.remove(); marker = null; } },
      onMapClick(fn){ map.on('click', e => fn(e.latlng.lat, e.latlng.lng > 180 ? e.latlng.lng - 360 : e.latlng.lng)); },
      center(lat, lon, zoom){ map.setView(ll(lat, lon), zoom || map.getZoom()); },
      resize(){ map.invalidateSize(); }
    };
    return api;
  }
  const toLeaflet = s => ({fillColor:s.fill, fillOpacity:s.fillOpacity, color:s.stroke, weight:s.weight, opacity:s.opacity ?? 1});

  /* ---------------- Google Maps ---------------- */
  // Google reports a rejected key (API not enabled, wrong referrer, no billing) through gm_authFailure and an error
  // overlay, not through a failed script load, so both are watched.
  let googleRejected = false;
  const prevAuthFailure = window.gm_authFailure;
  window.gm_authFailure = () => { googleRejected = true; if (prevAuthFailure) prevAuthFailure(); };
  // Some key problems (ApiNotActivatedMapError, BillingNotEnabledMapError...) are only reported as a console error.
  const consoleError = console.error;
  console.error = function(...args){
    if (args.some(a => /Google Maps JavaScript API error: \w+MapError/.test(String(a)))) googleRejected = true;
    return consoleError.apply(this, args);
  };

  async function google(el, key){
    if (googleRejected) throw new Error('Google Maps key was rejected earlier');
    if (!window.google?.maps?.Map){
      await new Promise((ok, fail) => {
        window.__vvMapsReady = ok;
        load('script', {src:'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(key) + '&v=weekly&libraries=marker&loading=async&callback=__vvMapsReady', async:true}).catch(fail);
      });
    }
    const g = window.google.maps;
    const map = new g.Map(el, {center:{lat:20, lng:78}, zoom:4, mapId:'DEMO_MAP_ID', gestureHandling:'greedy',
      streetViewControl:false, mapTypeControl:false, fullscreenControl:false, clickableIcons:false});
    // Wait until the map really draws; give up on a rejected key so the caller can fall back to OpenStreetMap.
    // Google can report "tiles loaded" for its blank placeholder tiles and log the key error just after, so a short
    // grace period follows tilesloaded before the map is trusted.
    await new Promise((ok, fail) => {
      const started = Date.now();
      let loadedAt = null;
      g.event.addListenerOnce(map, 'tilesloaded', () => { loadedAt = Date.now(); });
      const poll = setInterval(() => {
        const broken = googleRejected || el.querySelector('.gm-err-container, .gm-err-message');
        if (broken){ clearInterval(poll); fail(new Error('Google Maps rejected the key (see the console for the reason)')); }
        else if (loadedAt && Date.now() - loadedAt > 1500){ clearInterval(poll); ok(); }
        // Nothing drawn at all: a key without the Maps JavaScript API enabled behaves like this.
        else if (Date.now() - started > 8000){ clearInterval(poll); fail(new Error('Google Maps did not draw within 8 s')); }
      }, 150);
    });
    const points = new g.Data({map});
    let pins = [], marker = null, styleFn = null, tipFn = null;
    const tip = document.createElement('div'); tip.className = 'vv-tip vv-gtip'; el.appendChild(tip);
    map.data.addListener('mousemove', e => {
      if (!tipFn) return;
      tip.textContent = tipFn(e.feature.getProperty('admin_code'));
      const r = el.getBoundingClientRect(); tip.style.left = (e.domEvent.clientX - r.left + 12) + 'px'; tip.style.top = (e.domEvent.clientY - r.top + 12) + 'px';
      tip.style.display = 'block';
    });
    map.data.addListener('mouseout', () => { tip.style.display = 'none'; });
    const api = {
      provider:'google',
      setAreas(geo, {onClick, tip:t} = {}){
        map.data.forEach(f => map.data.remove(f));
        map.data.addGeoJson(geo); tipFn = t;
        g.event.clearListeners(map.data, 'click');
        if (onClick) map.data.addListener('click', e => onClick(e.feature.getProperty('admin_code')));
      },
      styleAreas(fn){
        styleFn = fn;
        map.data.setStyle(f => { const s = fn(f.getProperty('admin_code'));
          return {fillColor:s.fill, fillOpacity:s.fillOpacity, strokeColor:s.stroke, strokeWeight:s.weight, strokeOpacity:s.opacity ?? 1, zIndex:s.weight > 1.5 ? 2 : 1}; });
      },
      fitCodes(codes){
        const b = new g.LatLngBounds(); let any = false;
        map.data.forEach(f => { if (!codes || codes.includes(f.getProperty('admin_code'))){ f.getGeometry().forEachLatLng(p => { b.extend(p); any = true; }); } });
        if (any) map.fitBounds(b, 24);
      },
      setPoints(list){
        points.forEach(f => points.remove(f));
        points.addGeoJson({type:'FeatureCollection', features:list.map(p => ({type:'Feature', geometry:{type:'Point', coordinates:[p.lon, p.lat]}, properties:{c:p.color, r:p.r || 4}}))});
        points.setStyle(f => ({clickable:false, icon:{path:g.SymbolPath.CIRCLE, scale:f.getProperty('r'), fillColor:f.getProperty('c'), fillOpacity:.75, strokeWeight:0}}));
      },
      setPins(list){
        pins.forEach(m => m.map = null);
        pins = list.map(p => {
          const div = document.createElement('div'); div.innerHTML = pinHtml(p);
          const m = new g.marker.AdvancedMarkerElement({map, position:{lat:p.lat, lng:p.lon}, content:div.firstChild, zIndex:p.cls?.includes('on') ? 1000 : 1, gmpClickable:!!p.onClick});
          if (p.onClick) m.addEventListener('gmp-click', p.onClick);
          return m;
        });
      },
      setMarker({lat, lon, draggable, onMove}){
        if (!marker){
          const div = document.createElement('div'); div.className = 'dropper';
          marker = new g.marker.AdvancedMarkerElement({map, position:{lat, lng:lon}, gmpDraggable:!!draggable, content:div});
          marker.addListener('dragend', () => { const p = marker.position; onMove && onMove(typeof p.lat === 'function' ? p.lat() : p.lat, typeof p.lng === 'function' ? p.lng() : p.lng); });
        } else marker.position = {lat, lng:lon};
        map.setCenter({lat, lng:lon}); if (map.getZoom() < 15) map.setZoom(15);
      },
      clearMarker(){ if (marker){ marker.map = null; marker = null; } },
      onMapClick(fn){ map.addListener('click', e => fn(e.latLng.lat(), e.latLng.lng())); map.data.addListener('click', e => fn(e.latLng.lat(), e.latLng.lng())); },
      center(lat, lon, zoom){ map.setCenter({lat, lng:lon}); if (zoom) map.setZoom(zoom); },
      resize(){ g.event.trigger(map, 'resize'); }
    };
    return api;
  }

  window.VVMap = {
    async create(el, config){
      const key = config?.maps?.provider === 'google' && config.maps.browser_key;
      if (key){
        try { return await google(el, key); }
        catch (e) {
          console.warn('Google Maps is unavailable, using OpenStreetMap instead:', e.message);
          const fresh = el.cloneNode(false);  // drop Google's leftovers; same id and classes
          el.replaceWith(fresh); el = fresh;
        }
      }
      return leaflet(el);
    }
  };
})();

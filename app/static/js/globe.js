/**
 * UptimeNode Professional Globe v2
 * Wireframe globe with green/red connection lines
 * 20 cities including Algiers
 */
(function() {
    const canvas = document.getElementById('globe-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let W, H, cx, cy, R;
    let rotY = 0;
    let rotX = -0.25;
    let time = 0;
    let sites = window.monitoringSites || [];

    const cities = [
        { name: 'Algiers', lat: 36.75, lon: 3.04 },
        { name: 'New York', lat: 40.71, lon: -74.00 },
        { name: 'London', lat: 51.51, lon: -0.13 },
        { name: 'Tokyo', lat: 35.68, lon: 139.69 },
        { name: 'Sydney', lat: -33.87, lon: 151.21 },
        { name: 'Paris', lat: 48.86, lon: 2.35 },
        { name: 'Moscow', lat: 55.76, lon: 37.62 },
        { name: 'Singapore', lat: 1.35, lon: 103.82 },
        { name: 'Sao Paulo', lat: -23.55, lon: -46.63 },
        { name: 'Dubai', lat: 25.20, lon: 55.27 },
        { name: 'Mumbai', lat: 19.08, lon: 72.88 },
        { name: 'Cairo', lat: 30.04, lon: 31.24 },
        { name: 'Beijing', lat: 39.90, lon: 116.40 },
        { name: 'Lagos', lat: 6.52, lon: 3.38 },
        { name: 'Mexico City', lat: 19.43, lon: -99.13 },
        { name: 'Berlin', lat: 52.52, lon: 13.41 },
        { name: 'Seoul', lat: 37.57, lon: 126.98 },
        { name: 'Toronto', lat: 43.65, lon: -79.38 },
        { name: 'Bangkok', lat: 13.76, lon: 100.50 },
        { name: 'Istanbul', lat: 41.01, lon: 28.98 }
    ];

    const connections = [];
    for (let i = 0; i < cities.length; i++) {
        for (let j = i + 1; j < cities.length; j++) {
            const dlat = cities[i].lat - cities[j].lat;
            const dlon = cities[i].lon - cities[j].lon;
            const dist = Math.sqrt(dlat * dlat + dlon * dlon);
            if (dist < 70 && Math.random() > 0.35) {
                connections.push({
                    from: i, to: j,
                    progress: Math.random(),
                    speed: 0.002 + Math.random() * 0.005
                });
            }
        }
    }

    function resize() {
        const parent = canvas.parentElement;
        W = canvas.width = parent.offsetWidth;
        H = canvas.height = parent.offsetHeight;
        cx = W / 2;
        cy = H / 2;
        R = Math.min(W, H) * 0.38;
    }

    function latLonTo3D(lat, lon) {
        const latR = lat * Math.PI / 180;
        const lonR = lon * Math.PI / 180;
        const x = R * Math.cos(latR) * Math.sin(lonR);
        const y = -R * Math.sin(latR);
        const z = R * Math.cos(latR) * Math.cos(lonR);
        return rotate(x, y, z);
    }

    function rotate(x, y, z) {
        let x1 = x * Math.cos(rotY) - z * Math.sin(rotY);
        let z1 = x * Math.sin(rotY) + z * Math.cos(rotY);
        let y1 = y * Math.cos(rotX) - z1 * Math.sin(rotX);
        let z2 = y * Math.sin(rotX) + z1 * Math.cos(rotX);
        return { x: x1, y: y1, z: z2 };
    }

    function project(p) {
        const s = 600 / (600 + p.z);
        return { x: cx + p.x * s, y: cy + p.y * s, z: p.z, s: s };
    }

    function getColor() {
        const hasDown = sites.some(s => s.status === 'down');
        return hasDown ? [248, 113, 113] : [0, 255, 102];
    }

    function drawVignette() {
        const grad = ctx.createRadialGradient(cx, cy, R * 0.5, cx, cy, Math.max(W, H) * 0.7);
        grad.addColorStop(0, 'rgba(0,0,0,0)');
        grad.addColorStop(1, 'rgba(0,0,0,0.6)');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);
    }

    function drawGrid() {
        ctx.strokeStyle = 'rgba(0, 255, 102, 0.04)';
        ctx.lineWidth = 0.5;
        const size = 40;
        for (let x = 0; x < W; x += size) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, H);
            ctx.stroke();
        }
        for (let y = 0; y < H; y += size) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(W, y);
            ctx.stroke();
        }
    }

    function drawGlobe() {
        const glow = ctx.createRadialGradient(cx, cy, R * 0.3, cx, cy, R * 1.8);
        glow.addColorStop(0, 'rgba(0, 255, 102, 0.04)');
        glow.addColorStop(0.5, 'rgba(0, 255, 102, 0.015)');
        glow.addColorStop(1, 'rgba(0, 255, 102, 0)');
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(cx, cy, R * 1.8, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = 'rgba(0, 255, 102, 0.2)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, Math.PI * 2);
        ctx.stroke();
    }

    function drawWireframe() {
        ctx.strokeStyle = 'rgba(0, 255, 102, 0.08)';
        ctx.lineWidth = 0.4;

        for (let lat = -60; lat <= 60; lat += 20) {
            ctx.beginPath();
            let first = true;
            for (let lon = 0; lon <= 360; lon += 4) {
                const p = project(latLonTo3D(lat, lon));
                if (p.z > -R * 0.1) {
                    if (first) { ctx.moveTo(p.x, p.y); first = false; }
                    else ctx.lineTo(p.x, p.y);
                } else first = true;
            }
            ctx.stroke();
        }

        for (let lon = 0; lon < 360; lon += 20) {
            ctx.beginPath();
            let first = true;
            for (let lat = -90; lat <= 90; lat += 4) {
                const p = project(latLonTo3D(lat, lon));
                if (p.z > -R * 0.1) {
                    if (first) { ctx.moveTo(p.x, p.y); first = false; }
                    else ctx.lineTo(p.x, p.y);
                } else first = true;
            }
            ctx.stroke();
        }
    }

    function drawConnections() {
        const color = getColor();

        connections.forEach(conn => {
            const p1 = project(latLonTo3D(cities[conn.from].lat, cities[conn.from].lon));
            const p2 = project(latLonTo3D(cities[conn.to].lat, cities[conn.to].lon));

            if (p1.z > -R * 0.2 && p2.z > -R * 0.2) {
                const op = Math.min(
                    0.1 + (p1.z + R) / (2 * R) * 0.25,
                    0.1 + (p2.z + R) / (2 * R) * 0.25
                );

                const mx = (p1.x + p2.x) / 2;
                const my = (p1.y + p2.y) / 2 - 25;

                ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${op})`;
                ctx.lineWidth = 0.8;
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.quadraticCurveTo(mx, my, p2.x, p2.y);
                ctx.stroke();

                conn.progress += conn.speed;
                if (conn.progress >= 1) conn.progress = 0;

                const t = conn.progress;
                const px = (1-t)*(1-t)*p1.x + 2*(1-t)*t*mx + t*t*p2.x;
                const py = (1-t)*(1-t)*p1.y + 2*(1-t)*t*my + t*t*p2.y;

                ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${op * 2.5})`;
                ctx.beginPath();
                ctx.arc(px, py, 1.2, 0, Math.PI * 2);
                ctx.fill();
            }
        });
    }

    function drawCities() {
        const color = getColor();

        cities.forEach((city, i) => {
            const p = project(latLonTo3D(city.lat, city.lon));

            if (p.z > -R * 0.2) {
                const op = 0.25 + (p.z + R) / (2 * R) * 0.75;
                const pulse = 1 + Math.sin(time * 3 + i * 0.7) * 0.4;

                const gs = 14 * pulse * p.s;
                const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, gs);
                glow.addColorStop(0, `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${op * 0.35})`);
                glow.addColorStop(1, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0)`);
                ctx.fillStyle = glow;
                ctx.beginPath();
                ctx.arc(p.x, p.y, gs, 0, Math.PI * 2);
                ctx.fill();

                ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${op})`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, 2.5 * p.s, 0, Math.PI * 2);
                ctx.fill();

                ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${op * 0.25})`;
                ctx.lineWidth = 0.8;
                ctx.beginPath();
                ctx.arc(p.x, p.y, 7 * pulse * p.s, 0, Math.PI * 2);
                ctx.stroke();
            }
        });
    }

    function drawHUD() {
        ctx.fillStyle = 'rgba(0, 255, 102, 0.5)';
        ctx.font = '10px monospace';
        ctx.fillText('SITEWATCH MONITORING', 20, 30);
        ctx.fillText('STATUS: ' + (sites.some(s => s.status === 'down') ? 'ALERT' : 'ALL SYSTEMS ONLINE'), 20, 45);

        ctx.strokeStyle = 'rgba(0, 255, 102, 0.15)';
        ctx.lineWidth = 1;
        ctx.strokeRect(15, 15, 200, 45);

        ctx.fillStyle = 'rgba(0, 255, 102, 0.5)';
        ctx.fillText('NODES: ' + cities.length, 20, H - 30);
        ctx.fillText('LATENCY: ' + Math.floor(50 + Math.sin(time) * 20) + 'ms', 20, H - 15);
        ctx.strokeRect(15, H - 40, 160, 35);
    }

    function draw() {
        ctx.clearRect(0, 0, W, H);
        drawGrid();
        drawGlobe();
        drawWireframe();
        drawConnections();
        drawCities();
        drawVignette();
        drawHUD();
    }

    function update() {
        rotY += 0.002;
        time += 0.016;
    }

    function animate() {
        update();
        draw();
        requestAnimationFrame(animate);
    }

    function init() {
        resize();
        animate();
        window.addEventListener('resize', resize);
    }

    window.UptimeNodeGlobe = {
        setSites: function(s) { sites = s; }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

/**
 * SiteWatch Professional Globe Animation
 * Digital wireframe globe with connecting lines
 */
(function() {
    const canvas = document.getElementById('globe-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let W, H, cx, cy, R;
    let rotationY = 0;
    let rotationX = -0.3;
    let time = 0;
    let mouse = { x: 0, y: 0 };
    let sites = window.monitoringSites || [];
    let animationId;

    // City locations (lat, lon)
    const cities = [
        { name: 'New York', lat: 40.71, lon: -74.00 },
        { name: 'London', lat: 51.51, lon: -0.13 },
        { name: 'Tokyo', lat: 35.68, lon: 139.69 },
        { name: 'Sydney', lat: -33.87, lon: 151.21 },
        { name: 'Paris', lat: 48.86, lon: 2.35 },
        { name: 'Moscow', lat: 55.76, lon: 37.62 },
        { name: 'Singapore', lat: 1.35, lon: 103.82 },
        { name: 'São Paulo', lat: -23.55, lon: -46.63 },
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
        { name: 'Istanbul', lat: 41.01, lon: 28.98 },
        { name: 'Nairobi', lat: -1.29, lon: 36.82 }
    ];

    // Connection lines between cities
    const connections = [];
    for (let i = 0; i < cities.length; i++) {
        for (let j = i + 1; j < cities.length; j++) {
            const dlat = cities[i].lat - cities[j].lat;
            const dlon = cities[i].lon - cities[j].lon;
            const dist = Math.sqrt(dlat * dlat + dlon * dlon);
            if (dist < 80 && Math.random() > 0.4) {
                connections.push({ from: i, to: j, progress: Math.random(), speed: 0.003 + Math.random() * 0.004 });
            }
        }
    }

    function resize() {
        const parent = canvas.parentElement;
        W = canvas.width = parent.offsetWidth;
        H = canvas.height = parent.offsetHeight;
        cx = W / 2;
        cy = H / 2;
        R = Math.min(W, H) * 0.35;
    }

    function latLonTo3D(lat, lon) {
        const latR = lat * Math.PI / 180;
        const lonR = lon * Math.PI / 180;
        const x = R * Math.cos(latR) * Math.sin(lonR);
        const y = -R * Math.sin(latR);
        const z = R * Math.cos(latR) * Math.cos(lonR);
        return rotate3D(x, y, z);
    }

    function rotate3D(x, y, z) {
        // Rotate around Y axis
        let x1 = x * Math.cos(rotationY) - z * Math.sin(rotationY);
        let z1 = x * Math.sin(rotationY) + z * Math.cos(rotationY);
        // Rotate around X axis
        let y1 = y * Math.cos(rotationX) - z1 * Math.sin(rotationX);
        let z2 = y * Math.sin(rotationX) + z1 * Math.cos(rotationX);
        return { x: x1, y: y1, z: z2 };
    }

    function project(p) {
        const scale = 600 / (600 + p.z);
        return {
            x: cx + p.x * scale,
            y: cy + p.y * scale,
            z: p.z,
            scale: scale
        };
    }

    function drawGlobe() {
        // Outer glow
        const glowGrad = ctx.createRadialGradient(cx, cy, R * 0.5, cx, cy, R * 2);
        glowGrad.addColorStop(0, 'rgba(34, 197, 94, 0.06)');
        glowGrad.addColorStop(0.5, 'rgba(34, 197, 94, 0.02)');
        glowGrad.addColorStop(1, 'rgba(34, 197, 94, 0)');
        ctx.fillStyle = glowGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, R * 2, 0, Math.PI * 2);
        ctx.fill();

        // Globe outline
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.4)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, Math.PI * 2);
        ctx.stroke();

        // Globe inner glow
        const innerGrad = ctx.createRadialGradient(cx - R * 0.3, cy - R * 0.3, 0, cx, cy, R);
        innerGrad.addColorStop(0, 'rgba(34, 197, 94, 0.08)');
        innerGrad.addColorStop(1, 'rgba(34, 197, 94, 0.01)');
        ctx.fillStyle = innerGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawGrid() {
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.12)';
        ctx.lineWidth = 0.5;

        // Latitude lines
        for (let lat = -60; lat <= 60; lat += 20) {
            ctx.beginPath();
            let first = true;
            for (let lon = 0; lon <= 360; lon += 3) {
                const p = project(latLonTo3D(lat, lon));
                if (p.z > -R * 0.2) {
                    if (first) { ctx.moveTo(p.x, p.y); first = false; }
                    else ctx.lineTo(p.x, p.y);
                } else {
                    first = true;
                }
            }
            ctx.stroke();
        }

        // Longitude lines
        for (let lon = 0; lon < 360; lon += 20) {
            ctx.beginPath();
            let first = true;
            for (let lat = -90; lat <= 90; lat += 3) {
                const p = project(latLonTo3D(lat, lon));
                if (p.z > -R * 0.2) {
                    if (first) { ctx.moveTo(p.x, p.y); first = false; }
                    else ctx.lineTo(p.x, p.y);
                } else {
                    first = true;
                }
            }
            ctx.stroke();
        }
    }

    function drawConnections() {
        const hasDown = sites.some(s => s.status === 'down');
        const color = hasDown ? [248, 113, 113] : [34, 197, 94];

        connections.forEach(conn => {
            const from = cities[conn.from];
            const to = cities[conn.to];
            const p1 = project(latLonTo3D(from.lat, from.lon));
            const p2 = project(latLonTo3D(to.lat, to.lon));

            if (p1.z > -R * 0.3 && p2.z > -R * 0.3) {
                const opacity = Math.min(
                    0.15 + (p1.z + R) / (2 * R) * 0.35,
                    0.15 + (p2.z + R) / (2 * R) * 0.35
                );

                // Curved line
                const mx = (p1.x + p2.x) / 2;
                const my = (p1.y + p2.y) / 2 - 20;

                ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${opacity})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.quadraticCurveTo(mx, my, p2.x, p2.y);
                ctx.stroke();

                // Animated particle
                conn.progress += conn.speed;
                if (conn.progress >= 1) conn.progress = 0;

                const t = conn.progress;
                const px = (1-t)*(1-t)*p1.x + 2*(1-t)*t*mx + t*t*p2.x;
                const py = (1-t)*(1-t)*p1.y + 2*(1-t)*t*my + t*t*p2.y;

                ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${opacity * 2})`;
                ctx.beginPath();
                ctx.arc(px, py, 1.5, 0, Math.PI * 2);
                ctx.fill();
            }
        });
    }

    function drawCities() {
        const hasDown = sites.some(s => s.status === 'down');
        const color = hasDown ? [248, 113, 113] : [34, 197, 94];

        cities.forEach((city, i) => {
            const p = project(latLonTo3D(city.lat, city.lon));

            if (p.z > -R * 0.3) {
                const opacity = 0.3 + (p.z + R) / (2 * R) * 0.7;
                const pulse = 1 + Math.sin(time * 3 + i * 0.5) * 0.3;

                // Glow
                const glowSize = 12 * pulse * p.scale;
                const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, glowSize);
                glow.addColorStop(0, `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${opacity * 0.4})`);
                glow.addColorStop(1, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0)`);
                ctx.fillStyle = glow;
                ctx.beginPath();
                ctx.arc(p.x, p.y, glowSize, 0, Math.PI * 2);
                ctx.fill();

                // Dot
                ctx.fillStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${opacity})`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, 2.5 * p.scale, 0, Math.PI * 2);
                ctx.fill();

                // Ring
                ctx.strokeStyle = `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${opacity * 0.3})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(p.x, p.y, 6 * pulse * p.scale, 0, Math.PI * 2);
                ctx.stroke();
            }
        });
    }

    function drawFloatingParticles() {
        const hasDown = sites.some(s => s.status === 'down');
        const color = hasDown ? [248, 113, 113] : [34, 197, 94];

        for (let i = 0; i < 5; i++) {
            const angle = time * 0.3 + (i * Math.PI * 2) / 5;
            const dist = R * 1.4 + Math.sin(time + i) * 20;
            const x = cx + Math.cos(angle) * dist;
            const y = cy + Math.sin(angle * 0.5) * dist * 0.3;

            const glow = ctx.createRadialGradient(x, y, 0, x, y, 20);
            glow.addColorStop(0, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.3)`);
            glow.addColorStop(1, `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0)`);
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(x, y, 20, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    function draw() {
        ctx.clearRect(0, 0, W, H);

        drawGlobe();
        drawGrid();
        drawConnections();
        drawCities();
        drawFloatingParticles();
    }

    function update() {
        rotationY += 0.002;
        time += 0.016;
    }

    function animate() {
        update();
        draw();
        animationId = requestAnimationFrame(animate);
    }

    function init() {
        resize();
        animate();
        window.addEventListener('resize', resize);

        canvas.parentElement.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            mouse.x = ((e.clientX - rect.left) / W - 0.5) * 0.5;
            mouse.y = ((e.clientY - rect.top) / H - 0.5) * 0.5;
        });
    }

    window.SiteWatchGlobe = {
        setSites: function(newSites) { sites = newSites; },
        destroy: function() { if (animationId) cancelAnimationFrame(animationId); }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

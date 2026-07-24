/**
 * SiteWatch 3D Tactical HUD Background
 * Three.js Cybersecurity Globe — MW3 Style
 * Full-screen fixed background, auto-rotate, breathing camera
 */
(function () {
    const container = document.getElementById('globe-bg');
    if (!container) return;

    /* ── CDN inject ─────────────────────────────────────────── */
    if (!window.THREE) {
        var s = document.createElement('script');
        s.src = 'https://unpkg.com/three@0.160.0/build/three.module.min.js';
        s.onload = initGlobe;
        document.head.appendChild(s);
    } else {
        initGlobe();
    }

    function initGlobe() {
        const THREE = window.THREE;
        const isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) || window.innerWidth < 768;

        /* ── Scene ───────────────────────────────────────────── */
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x050505);

        /* ── Camera ──────────────────────────────────────────── */
        const camera = new THREE.PerspectiveCamera(
            isMobile ? 55 : 45,
            window.innerWidth / window.innerHeight,
            0.1,
            1000
        );
        camera.position.z = isMobile ? 4.2 : 3.4;

        /* ── Renderer ────────────────────────────────────────── */
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        container.appendChild(renderer.domElement);

        /* ── Colors ──────────────────────────────────────────── */
        const SAFE = new THREE.Color(0x00ff66);
        const DANGER = new THREE.Color(0xff0000);
        const DIM = new THREE.Color(0x00ff66);

        /* ── Globe wireframe ─────────────────────────────────── */
        const globeRadius = 1.6;
        const globeGeo = new THREE.SphereGeometry(globeRadius, 40, 30);
        const globeMat = new THREE.MeshBasicMaterial({
            color: SAFE,
            wireframe: true,
            transparent: true,
            opacity: 0.07
        });
        const globe = new THREE.Mesh(globeGeo, globeMat);
        scene.add(globe);

        /* ── Atmosphere ring ─────────────────────────────────── */
        const atmoGeo = new THREE.SphereGeometry(globeRadius * 1.04, 60, 40);
        const atmoMat = new THREE.MeshBasicMaterial({
            color: SAFE,
            wireframe: true,
            transparent: true,
            opacity: 0.03
        });
        const atmosphere = new THREE.Mesh(atmoGeo, atmoMat);
        scene.add(atmosphere);

        /* ── Cities data ─────────────────────────────────────── */
        function latLonToVec3(lat, lon, r) {
            const phi = (90 - lat) * (Math.PI / 180);
            const theta = (lon + 180) * (Math.PI / 180);
            return new THREE.Vector3(
                -r * Math.sin(phi) * Math.cos(theta),
                 r * Math.cos(phi),
                 r * Math.sin(phi) * Math.sin(theta)
            );
        }

        const cities = [
            { name: 'Algiers',      lat: 36.75,  lon: 3.04,    safe: true  },
            { name: 'New York',     lat: 40.71,  lon: -74.00,  safe: true  },
            { name: 'London',       lat: 51.51,  lon: -0.13,   safe: true  },
            { name: 'Tokyo',        lat: 35.68,  lon: 139.69,  safe: true  },
            { name: 'Sydney',       lat: -33.87, lon: 151.21,  safe: true  },
            { name: 'Paris',        lat: 48.86,  lon: 2.35,    safe: true  },
            { name: 'Moscow',       lat: 55.76,  lon: 37.62,   safe: true  },
            { name: 'Singapore',    lat: 1.35,   lon: 103.82,  safe: true  },
            { name: 'Sao Paulo',    lat: -23.55, lon: -46.63,  safe: true  },
            { name: 'Dubai',        lat: 25.20,  lon: 55.27,   safe: true  },
            { name: 'Mumbai',       lat: 19.08,  lon: 72.88,   safe: true  },
            { name: 'Cairo',        lat: 30.04,  lon: 31.24,   safe: true  },
            { name: 'Beijing',      lat: 39.90,  lon: 116.40,  safe: true  },
            { name: 'Lagos',        lat: 6.52,   lon: 3.38,    safe: true  },
            { name: 'Mexico City',  lat: 19.43,  lon: -99.13,  safe: true  },
            { name: 'Berlin',       lat: 52.52,  lon: 13.41,   safe: true  },
            { name: 'Seoul',        lat: 37.57,  lon: 126.98,  safe: true  },
            { name: 'Toronto',      lat: 43.65,  lon: -79.38,  safe: true  },
            { name: 'Bangkok',      lat: 13.76,  lon: 100.50,  safe: true  },
            { name: 'Istanbul',     lat: 41.01,  lon: 28.98,   safe: true  }
        ];

        /* ── Node dots ───────────────────────────────────────── */
        const nodeGroup = new THREE.Group();
        scene.add(nodeGroup);

        const dotGeo = new THREE.SphereGeometry(isMobile ? 0.022 : 0.028, 8, 8);

        const nodes = cities.map(function (c) {
            const col = c.safe ? SAFE.clone() : DANGER.clone();
            const mat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.95 });
            const dot = new THREE.Mesh(dotGeo, mat);
            const pos = latLonToVec3(c.lat, c.lon, globeRadius * 1.005);
            dot.position.copy(pos);
            nodeGroup.add(dot);

            /* glow ring */
            const ringGeo = new THREE.RingGeometry(0.035, 0.06, 24);
            const ringMat = new THREE.MeshBasicMaterial({
                color: col, transparent: true, opacity: 0.35, side: THREE.DoubleSide
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.position.copy(pos);
            ring.lookAt(new THREE.Vector3(0, 0, 0));
            nodeGroup.add(ring);

            return { city: c, dot: dot, ring: ring, pos: pos, mat: mat, ringMat: ringMat };
        });

        /* ── Connections ─────────────────────────────────────── */
        const lineGroup = new THREE.Group();
        scene.add(lineGroup);

        function buildConnections() {
            while (lineGroup.children.length) lineGroup.remove(lineGroup.children[0]);

            var maxLines = isMobile ? 5 : 25;
            var drawn = 0;

            for (var i = 0; i < cities.length && drawn < maxLines; i++) {
                for (var j = i + 1; j < cities.length && drawn < maxLines; j++) {
                    var dlat = cities[i].lat - cities[j].lat;
                    var dlon = cities[i].lon - cities[j].lon;
                    var dist = Math.sqrt(dlat * dlat + dlon * dlon);
                    if (dist > 65) continue;
                    if (Math.random() < 0.3) continue;

                    var bothSafe = cities[i].safe && cities[j].safe;
                    var col = bothSafe ? SAFE : DANGER;

                    var pts = [];
                    var p1 = latLonToVec3(cities[i].lat, cities[i].lon, globeRadius * 1.005);
                    var p2 = latLonToVec3(cities[j].lat, cities[j].lon, globeRadius * 1.005);
                    var mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
                    mid.normalize().multiplyScalar(globeRadius * 1.18);

                    var curve = new THREE.QuadraticBezierCurve3(p1, mid, p2);
                    var segs = isMobile ? 16 : 28;
                    pts = curve.getPoints(segs);

                    var geo = new THREE.BufferGeometry().setFromPoints(pts);
                    var mat = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.35 });
                    var line = new THREE.Line(geo, mat);
                    lineGroup.add(line);
                    drawn++;

                    /* animated pulse dot on the line */
                    var pulseGeo = new THREE.SphereGeometry(0.012, 6, 6);
                    var pulseMat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.8 });
                    var pulse = new THREE.Mesh(pulseGeo, pulseMat);
                    lineGroup.add(pulse);

                    pulse.userData = { curve: curve, t: Math.random(), speed: 0.002 + Math.random() * 0.004 };
                }
            }
        }
        buildConnections();

        /* ── Particles ───────────────────────────────────────── */
        var pCount = isMobile ? 150 : 350;
        var pGeo = new THREE.BufferGeometry();
        var pPositions = new Float32Array(pCount * 3);
        var pSizes = new Float32Array(pCount);
        for (var i = 0; i < pCount; i++) {
            pPositions[i * 3]     = (Math.random() - 0.5) * 10;
            pPositions[i * 3 + 1] = (Math.random() - 0.5) * 10;
            pPositions[i * 3 + 2] = (Math.random() - 0.5) * 10;
            pSizes[i] = Math.random() * 1.5 + 0.5;
        }
        pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
        pGeo.setAttribute('size', new THREE.BufferAttribute(pSizes, 1));

        var pMat = new THREE.PointsMaterial({
            color: 0x00ff66,
            size: 0.015,
            transparent: true,
            opacity: 0.25,
            sizeAttenuation: true
        });
        var particles = new THREE.Points(pGeo, pMat);
        scene.add(particles);

        /* ── Lights for danger glow ──────────────────────────── */
        var dangerLight = new THREE.PointLight(0xff0000, 1.5, 4);
        dangerLight.position.set(0, 0, 0);
        scene.add(dangerLight);

        /* ── Animation loop ──────────────────────────────────── */
        var clock = new THREE.Clock();
        var breathBase = camera.position.z;

        function animate() {
            requestAnimationFrame(animate);
            var t = clock.getElapsedTime();

            /* globe rotate */
            globe.rotation.y += 0.0015;
            globe.rotation.x = Math.sin(t * 0.1) * 0.05;
            atmosphere.rotation.y = globe.rotation.y * 0.98;
            atmosphere.rotation.x = globe.rotation.x;
            nodeGroup.rotation.y = globe.rotation.y;
            nodeGroup.rotation.x = globe.rotation.x;

            /* breathing camera */
            camera.position.z = breathBase + Math.sin(t * 0.4) * 0.06;
            camera.position.y = Math.sin(t * 0.25) * 0.03;

            /* pulse danger nodes */
            nodes.forEach(function (n) {
                if (!n.city.safe) {
                    var s = 1 + Math.sin(t * 4) * 0.4;
                    n.dot.scale.set(s, s, s);
                    n.ringMat.opacity = 0.2 + Math.sin(t * 4) * 0.3;
                    n.dot.material.opacity = 0.6 + Math.sin(t * 4) * 0.4;
                }
            });

            /* animate pulse dots along lines */
            lineGroup.children.forEach(function (child) {
                if (child.userData && child.userData.curve) {
                    child.userData.t += child.userData.speed;
                    if (child.userData.t > 1) child.userData.t = 0;
                    var pt = child.userData.curve.getPointAt(child.userData.t);
                    child.position.copy(pt);
                }
            });

            /* particles drift */
            particles.rotation.y += 0.0003;
            particles.rotation.x += 0.0001;

            renderer.render(scene, camera);
        }
        animate();

        /* ── Resize ──────────────────────────────────────────── */
        window.addEventListener('resize', function () {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        });

        /* ── Public API for status updates ───────────────────── */
        window.SiteWatchGlobe3D = {
            setCityStatus: function (cityName, isSafe) {
                var node = nodes.find(function (n) { return n.city.name === cityName; });
                if (!node) return;
                node.city.safe = isSafe;
                var col = isSafe ? SAFE : DANGER;
                node.mat.color.copy(col);
                node.ringMat.color.copy(col);
                buildConnections();
            },
            setAllStatus: function (isSafe) {
                cities.forEach(function (c) { c.safe = isSafe; });
                nodes.forEach(function (n) {
                    var col = isSafe ? SAFE : DANGER;
                    n.mat.color.copy(col);
                    n.ringMat.color.copy(col);
                });
                buildConnections();
            }
        };
    }
})();

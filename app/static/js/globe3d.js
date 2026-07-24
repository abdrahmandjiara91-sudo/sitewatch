/**
 * SiteWatch 3D Tactical HUD Background
 * Three.js Cybersecurity Globe — MW3 Style
 * Reusable for landing + dashboard
 */
(function () {
    var container = document.getElementById('globe-bg');
    if (!container) return;

    if (!window.THREE) {
        var s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/three@0.150.1/build/three.min.js';
        s.onload = initGlobe;
        document.head.appendChild(s);
    } else {
        initGlobe();
    }

    function initGlobe() {
        var THREE = window.THREE;
        var isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) || window.innerWidth < 768;
        var isDashboard = container.getAttribute('data-dashboard') === 'true';

        var scene = new THREE.Scene();
        scene.background = null;

        var camera = new THREE.PerspectiveCamera(
            isMobile ? 60 : 48,
            container.clientWidth / container.clientHeight,
            0.1, 1000
        );
        camera.position.z = isMobile ? 4.0 : 3.2;

        var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);
        container.appendChild(renderer.domElement);

        var SAFE = new THREE.Color(0x00ff66);
        var DANGER = new THREE.Color(0xff0000);

        var globeRadius = 1.4;
        var globeGroup = new THREE.Group();
        scene.add(globeGroup);

        /* ── Globe wireframe ─────────────────────────────────── */
        var globeGeo = new THREE.SphereGeometry(globeRadius, 42, 28);
        var globeMat = new THREE.MeshBasicMaterial({
            color: SAFE, wireframe: true, transparent: true, opacity: 0.08
        });
        var globe = new THREE.Mesh(globeGeo, globeMat);
        globeGroup.add(globe);

        /* ── Atmosphere ──────────────────────────────────────── */
        var atmoGeo = new THREE.SphereGeometry(globeRadius * 1.03, 50, 35);
        var atmoMat = new THREE.MeshBasicMaterial({
            color: SAFE, wireframe: true, transparent: true, opacity: 0.025
        });
        var atmosphere = new THREE.Mesh(atmoGeo, atmoMat);
        globeGroup.add(atmosphere);

        /* ── Surface dots (Fibonacci sphere) ─────────────────── */
        var dotCount = isMobile ? 120 : 280;
        var surfaceDotGeo = new THREE.SphereGeometry(0.01, 4, 4);
        var surfaceDotMat = new THREE.MeshBasicMaterial({
            color: SAFE, transparent: true, opacity: 0.5
        });
        var surfaceDots = [];
        var goldenAngle = Math.PI * (3 - Math.sqrt(5));

        for (var i = 0; i < dotCount; i++) {
            var y = 1 - (i / (dotCount - 1)) * 2;
            var radiusAtY = Math.sqrt(1 - y * y);
            var theta = goldenAngle * i;
            var x = Math.cos(theta) * radiusAtY;
            var z = Math.sin(theta) * radiusAtY;

            var dot = new THREE.Mesh(surfaceDotGeo, surfaceDotMat.clone());
            dot.position.set(x * globeRadius * 1.003, y * globeRadius * 1.003, z * globeRadius * 1.003);
            globeGroup.add(dot);
            surfaceDots.push({ mesh: dot, baseOpacity: 0.3 + Math.random() * 0.35, idx: i });
        }

        /* ── Cities data ─────────────────────────────────────── */
        function latLonToVec3(lat, lon, r) {
            var phi = (90 - lat) * (Math.PI / 180);
            var theta = (lon + 180) * (Math.PI / 180);
            return new THREE.Vector3(
                -r * Math.sin(phi) * Math.cos(theta),
                r * Math.cos(phi),
                r * Math.sin(phi) * Math.sin(theta)
            );
        }

        var cities = [
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

        /* ── City node dots (bigger, with glow) ──────────────── */
        var nodeGroup = new THREE.Group();
        globeGroup.add(nodeGroup);

        var dotGeo = new THREE.SphereGeometry(isMobile ? 0.024 : 0.03, 8, 8);

        var nodes = cities.map(function (c) {
            var col = c.safe ? SAFE.clone() : DANGER.clone();
            var mat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.95 });
            var dot = new THREE.Mesh(dotGeo, mat);
            var pos = latLonToVec3(c.lat, c.lon, globeRadius * 1.005);
            dot.position.copy(pos);
            nodeGroup.add(dot);

            var ringGeo = new THREE.RingGeometry(0.038, 0.065, 24);
            var ringMat = new THREE.MeshBasicMaterial({
                color: col, transparent: true, opacity: 0.35, side: THREE.DoubleSide
            });
            var ring = new THREE.Mesh(ringGeo, ringMat);
            ring.position.copy(pos);
            ring.lookAt(new THREE.Vector3(0, 0, 0));
            nodeGroup.add(ring);

            return { city: c, dot: dot, ring: ring, pos: pos, mat: mat, ringMat: ringMat };
        });

        /* ── Connections ─────────────────────────────────────── */
        var lineGroup = new THREE.Group();
        globeGroup.add(lineGroup);

        function buildConnections() {
            while (lineGroup.children.length) lineGroup.remove(lineGroup.children[0]);
            var maxLines = isMobile ? 5 : 25;
            var drawn = 0;

            for (var i = 0; i < cities.length && drawn < maxLines; i++) {
                for (var j = i + 1; j < cities.length && drawn < maxLines; j++) {
                    var dlat = cities[i].lat - cities[j].lat;
                    var dlon = cities[i].lon - cities[j].lon;
                    var dist = Math.sqrt(dlat * dlat + dlon * dlon);
                    if (dist > 65 || Math.random() < 0.3) continue;

                    var bothSafe = cities[i].safe && cities[j].safe;
                    var col = bothSafe ? SAFE : DANGER;

                    var p1 = latLonToVec3(cities[i].lat, cities[i].lon, globeRadius * 1.005);
                    var p2 = latLonToVec3(cities[j].lat, cities[j].lon, globeRadius * 1.005);
                    var mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
                    mid.normalize().multiplyScalar(globeRadius * 1.2);
                    var curve = new THREE.QuadraticBezierCurve3(p1, mid, p2);

                    var pts = curve.getPoints(isMobile ? 16 : 28);
                    var geo = new THREE.BufferGeometry().setFromPoints(pts);
                    var mat = new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.35 });
                    lineGroup.add(new THREE.Line(geo, mat));

                    var pulseGeo = new THREE.SphereGeometry(0.012, 6, 6);
                    var pulseMat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.8 });
                    var pulse = new THREE.Mesh(pulseGeo, pulseMat);
                    pulse.userData = { curve: curve, t: Math.random(), speed: 0.002 + Math.random() * 0.004 };
                    lineGroup.add(pulse);
                    drawn++;
                }
            }
        }
        buildConnections();

        /* ── Floating particles ──────────────────────────────── */
        var pCount = isMobile ? 80 : 200;
        var pGeo = new THREE.BufferGeometry();
        var pPos = new Float32Array(pCount * 3);
        for (var i = 0; i < pCount; i++) {
            pPos[i * 3]     = (Math.random() - 0.5) * 8;
            pPos[i * 3 + 1] = (Math.random() - 0.5) * 8;
            pPos[i * 3 + 2] = (Math.random() - 0.5) * 8;
        }
        pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
        var pMat = new THREE.PointsMaterial({
            color: 0x00ff66, size: 0.012, transparent: true, opacity: 0.2, sizeAttenuation: true
        });
        var particles = new THREE.Points(pGeo, pMat);
        scene.add(particles);

        /* ── Animation ───────────────────────────────────────── */
        var clock = new THREE.Clock();
        var breathBase = camera.position.z;

        function animate() {
            requestAnimationFrame(animate);
            var t = clock.getElapsedTime();

            globeGroup.rotation.y += 0.0012;
            globeGroup.rotation.x = Math.sin(t * 0.08) * 0.04;

            camera.position.z = breathBase + Math.sin(t * 0.35) * 0.05;
            camera.position.y = Math.sin(t * 0.2) * 0.02;

            nodes.forEach(function (n) {
                if (!n.city.safe) {
                    var s = 1 + Math.sin(t * 4) * 0.4;
                    n.dot.scale.set(s, s, s);
                    n.ringMat.opacity = 0.2 + Math.sin(t * 4) * 0.3;
                }
            });

            surfaceDots.forEach(function (d) {
                d.mesh.material.opacity = d.baseOpacity + Math.sin(t * 1.5 + d.idx * 0.5) * 0.15;
            });

            lineGroup.children.forEach(function (child) {
                if (child.userData && child.userData.curve) {
                    child.userData.t += child.userData.speed;
                    if (child.userData.t > 1) child.userData.t = 0;
                    child.position.copy(child.userData.curve.getPointAt(child.userData.t));
                }
            });

            particles.rotation.y += 0.0002;
            particles.rotation.x += 0.0001;

            renderer.render(scene, camera);
        }
        animate();

        /* ── Resize ──────────────────────────────────────────── */
        window.addEventListener('resize', function () {
            var w = container.clientWidth;
            var h = container.clientHeight;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h);
        });

        /* ── Public API ──────────────────────────────────────── */
        window.SiteWatchGlobe3D = {
            setCityStatus: function (name, safe) {
                var n = nodes.find(function (x) { return x.city.name === name; });
                if (!n) return;
                n.city.safe = safe;
                var c = safe ? SAFE : DANGER;
                n.mat.color.copy(c);
                n.ringMat.color.copy(c);
                buildConnections();
            },
            setAllStatus: function (safe) {
                cities.forEach(function (c) { c.safe = safe; });
                nodes.forEach(function (n) {
                    var c = safe ? SAFE : DANGER;
                    n.mat.color.copy(c);
                    n.ringMat.color.copy(c);
                });
                buildConnections();
            }
        };
    }
})();

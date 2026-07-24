/**
 * SiteWatch Globe Animation
 * Animated globe with connection lines (green=UP, red=DOWN)
 */
class SiteWatchGlobe {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        
        this.width = 0;
        this.height = 0;
        this.rotation = 0;
        this.sites = options.sites || [];
        this.globeRadius = options.globeRadius || 150;
        this.centerX = 0;
        this.centerY = 0;
        
        // Colors
        this.colors = {
            globe: 'rgba(34, 197, 94, 0.08)',
            globeBorder: 'rgba(34, 197, 94, 0.3)',
            grid: 'rgba(34, 197, 94, 0.1)',
            up: '#4ade80',
            down: '#f87171',
            particle: 'rgba(34, 197, 94, 0.6)',
            glow: 'rgba(34, 197, 94, 0.2)'
        };
        
        this.particles = [];
        this.connections = [];
        this.time = 0;
        
        this.init();
    }
    
    init() {
        this.resize();
        this.createParticles();
        this.createConnections();
        window.addEventListener('resize', () => this.resize());
        this.animate();
    }
    
    resize() {
        const parent = this.canvas.parentElement;
        this.width = parent.offsetWidth;
        this.height = parent.offsetHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;
        this.centerX = this.width / 2;
        this.centerY = this.height / 2;
        
        // Adjust globe size based on screen
        const minDim = Math.min(this.width, this.height);
        this.globeRadius = Math.min(150, minDim * 0.3);
    }
    
    createParticles() {
        this.particles = [];
        const count = Math.min(80, Math.floor(this.width / 15));
        
        for (let i = 0; i < count; i++) {
            this.particles.push({
                lat: (Math.random() - 0.5) * Math.PI,
                lon: Math.random() * Math.PI * 2,
                size: Math.random() * 2 + 1,
                speed: Math.random() * 0.002 + 0.001,
                opacity: Math.random() * 0.5 + 0.3
            });
        }
    }
    
    createConnections() {
        this.connections = [];
        // Create connections between random particles
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                if (Math.random() > 0.85) {
                    this.connections.push({
                        from: i,
                        to: j,
                        progress: 0,
                        speed: Math.random() * 0.01 + 0.005,
                        active: false
                    });
                }
            }
        }
    }
    
    latLonTo3D(lat, lon) {
        const x = this.globeRadius * Math.cos(lat) * Math.cos(lon + this.rotation);
        const y = this.globeRadius * Math.sin(lat);
        const z = this.globeRadius * Math.cos(lat) * Math.sin(lon + this.rotation);
        return { x, y, z };
    }
    
    project(point3D) {
        const scale = 1.5;
        const z = point3D.z + this.globeRadius * 2;
        const factor = (this.globeRadius * scale) / z;
        return {
            x: this.centerX + point3D.x * factor,
            y: this.centerY - point3D.y * factor,
            z: point3D.z,
            scale: factor
        };
    }
    
    drawGlobe() {
        const ctx = this.ctx;
        
        // Globe glow
        const gradient = ctx.createRadialGradient(
            this.centerX, this.centerY, 0,
            this.centerX, this.centerY, this.globeRadius * 2
        );
        gradient.addColorStop(0, 'rgba(34, 197, 94, 0.05)');
        gradient.addColorStop(0.5, 'rgba(34, 197, 94, 0.02)');
        gradient.addColorStop(1, 'rgba(34, 197, 94, 0)');
        
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(this.centerX, this.centerY, this.globeRadius * 2, 0, Math.PI * 2);
        ctx.fill();
        
        // Globe circle
        ctx.strokeStyle = this.colors.globeBorder;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(this.centerX, this.centerY, this.globeRadius, 0, Math.PI * 2);
        ctx.stroke();
        
        // Globe fill
        ctx.fillStyle = this.colors.globe;
        ctx.fill();
        
        // Grid lines (latitude)
        ctx.strokeStyle = this.colors.grid;
        ctx.lineWidth = 0.5;
        
        for (let lat = -60; lat <= 60; lat += 30) {
            ctx.beginPath();
            const latRad = (lat * Math.PI) / 180;
            const radius = this.globeRadius * Math.cos(latRad);
            const yOffset = this.globeRadius * Math.sin(latRad);
            
            for (let lon = 0; lon <= 360; lon += 5) {
                const lonRad = (lon * Math.PI) / 180;
                const point = this.latLonTo3D(latRad, lonRad);
                const projected = this.project(point);
                
                if (lon === 0) {
                    ctx.moveTo(projected.x, projected.y);
                } else {
                    ctx.lineTo(projected.x, projected.y);
                }
            }
            ctx.stroke();
        }
        
        // Grid lines (longitude)
        for (let lon = 0; lon < 360; lon += 30) {
            ctx.beginPath();
            const lonRad = (lon * Math.PI) / 180;
            
            for (let lat = -90; lat <= 90; lat += 5) {
                const latRad = (lat * Math.PI) / 180;
                const point = this.latLonTo3D(latRad, lonRad);
                const projected = this.project(point);
                
                if (lat === -90) {
                    ctx.moveTo(projected.x, projected.y);
                } else {
                    ctx.lineTo(projected.x, projected.y);
                }
            }
            ctx.stroke();
        }
    }
    
    drawParticles() {
        const ctx = this.ctx;
        
        this.particles.forEach((p, i) => {
            const point = this.latLonTo3D(p.lat, p.lon);
            const projected = this.project(point);
            
            // Only draw if on front side
            if (point.z > -this.globeRadius * 0.3) {
                const opacity = p.opacity * (0.5 + (point.z + this.globeRadius) / (2 * this.globeRadius) * 0.5);
                
                // Particle glow
                const glowGradient = ctx.createRadialGradient(
                    projected.x, projected.y, 0,
                    projected.x, projected.y, p.size * 3
                );
                glowGradient.addColorStop(0, `rgba(34, 197, 94, ${opacity * 0.5})`);
                glowGradient.addColorStop(1, 'rgba(34, 197, 94, 0)');
                
                ctx.fillStyle = glowGradient;
                ctx.beginPath();
                ctx.arc(projected.x, projected.y, p.size * 3, 0, Math.PI * 2);
                ctx.fill();
                
                // Particle
                ctx.fillStyle = `rgba(34, 197, 94, ${opacity})`;
                ctx.beginPath();
                ctx.arc(projected.x, projected.y, p.size * projected.scale, 0, Math.PI * 2);
                ctx.fill();
            }
        });
    }
    
    drawConnections() {
        const ctx = this.ctx;
        
        this.connections.forEach(conn => {
            const from = this.particles[conn.from];
            const to = this.particles[conn.to];
            
            const fromPoint = this.latLonTo3D(from.lat, from.lon);
            const toPoint = this.latLonTo3D(to.lat, to.lon);
            
            const fromProj = this.project(fromPoint);
            const toProj = this.project(toPoint);
            
            // Only draw if both points are visible
            if (fromPoint.z > -this.globeRadius * 0.3 && toPoint.z > -this.globeRadius * 0.3) {
                const opacity = Math.min(
                    (0.5 + (fromPoint.z + this.globeRadius) / (2 * this.globeRadius) * 0.5),
                    (0.5 + (toPoint.z + this.globeRadius) / (2 * this.globeRadius) * 0.5)
                );
                
                // Determine color based on site status
                const hasDownSite = this.sites.some(s => s.status === 'down');
                const color = hasDownSite ? this.colors.down : this.colors.up;
                
                // Draw curved line
                const midX = (fromProj.x + toProj.x) / 2;
                const midY = (fromProj.y + toProj.y) / 2 - 30;
                
                ctx.strokeStyle = color.replace(')', `, ${opacity * 0.3})`).replace('rgb', 'rgba');
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(fromProj.x, fromProj.y);
                ctx.quadraticCurveTo(midX, midY, toProj.x, toProj.y);
                ctx.stroke();
                
                // Animated dot on line
                if (conn.active) {
                    conn.progress += conn.speed;
                    if (conn.progress >= 1) {
                        conn.progress = 0;
                        conn.active = false;
                    }
                    
                    const t = conn.progress;
                    const dotX = (1-t)*(1-t)*fromProj.x + 2*(1-t)*t*midX + t*t*toProj.x;
                    const dotY = (1-t)*(1-t)*fromProj.y + 2*(1-t)*t*midY + t*t*toProj.y;
                    
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(dotX, dotY, 2, 0, Math.PI * 2);
                    ctx.fill();
                } else if (Math.random() > 0.995) {
                    conn.active = true;
                    conn.progress = 0;
                }
            }
        });
    }
    
    drawSiteMarkers() {
        const ctx = this.ctx;
        
        // Fixed locations for demo (major cities)
        const locations = [
            { lat: 40.7, lon: -74, name: 'New York' },
            { lat: 51.5, lon: -0.1, name: 'London' },
            { lat: 35.7, lon: 139.7, name: 'Tokyo' },
            { lat: -33.9, lon: 151.2, name: 'Sydney' },
            { lat: 48.9, lon: 2.3, name: 'Paris' },
            { lat: 55.8, lon: 37.6, name: 'Moscow' },
            { lat: 1.3, lon: 103.8, name: 'Singapore' },
            { lat: -23.5, lon: -46.6, name: 'Sao Paulo' },
            { lat: 25.2, lon: 55.3, name: 'Dubai' },
            { lat: 19.4, lon: -99.1, name: 'Mexico City' }
        ];
        
        locations.forEach((loc, i) => {
            const point = this.latLonTo3D(
                (loc.lat * Math.PI) / 180,
                (loc.lon * Math.PI) / 180
            );
            const projected = this.project(point);
            
            if (point.z > -this.globeRadius * 0.3) {
                const opacity = 0.5 + (point.z + this.globeRadius) / (2 * this.globeRadius) * 0.5;
                const isUp = this.sites.length === 0 || !this.sites.some(s => s.status === 'down');
                const color = isUp ? this.colors.up : this.colors.down;
                
                // Pulsing ring
                const pulseSize = 8 + Math.sin(this.time * 2 + i) * 3;
                ctx.strokeStyle = color.replace(')', `, ${opacity * 0.3})`).replace('#', 'rgba(').replace(/([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i, (m, r, g, b) => {
                    return `${parseInt(r, 16)}, ${parseInt(g, 16)}, ${parseInt(b, 16)}`;
                });
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(projected.x, projected.y, pulseSize, 0, Math.PI * 2);
                ctx.stroke();
                
                // Center dot
                ctx.fillStyle = color;
                ctx.globalAlpha = opacity;
                ctx.beginPath();
                ctx.arc(projected.x, projected.y, 3, 0, Math.PI * 2);
                ctx.fill();
                ctx.globalAlpha = 1;
            }
        });
    }
    
    drawDataFlow() {
        const ctx = this.ctx;
        
        // Floating data particles
        for (let i = 0; i < 3; i++) {
            const angle = this.time * 0.5 + (i * Math.PI * 2) / 3;
            const radius = this.globeRadius * 1.3;
            const x = this.centerX + Math.cos(angle) * radius;
            const y = this.centerY + Math.sin(angle) * radius * 0.3;
            
            const gradient = ctx.createRadialGradient(x, y, 0, x, y, 15);
            gradient.addColorStop(0, 'rgba(34, 197, 94, 0.4)');
            gradient.addColorStop(1, 'rgba(34, 197, 94, 0)');
            
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(x, y, 15, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    
    update() {
        this.rotation += 0.003;
        this.time += 0.016;
        
        // Update particle positions
        this.particles.forEach(p => {
            p.lon += p.speed;
        });
    }
    
    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);
        
        this.drawGlobe();
        this.drawConnections();
        this.drawParticles();
        this.drawSiteMarkers();
        this.drawDataFlow();
    }
    
    animate() {
        this.update();
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
    
    setSites(sites) {
        this.sites = sites;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('globe-canvas');
    if (canvas) {
        window.globeAnimation = new SiteWatchGlobe('globe-canvas', {
            sites: window.monitoringSites || []
        });
    }
});

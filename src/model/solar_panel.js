import * as THREE from 'three';

export class SolarPanel {
    mesh;
    panel;
    constructor() {
        this.mesh = new THREE.Group();

        // Pole
        const pole = new THREE.Mesh(
            new THREE.CylinderGeometry(0.05, 0.05, 2, 8),
            new THREE.MeshPhongMaterial({ color: 0x666666 })
        );
        pole.position.y = 1;
        this.mesh.add(pole);

        // Mount
        const mount = new THREE.Mesh(
            new THREE.BoxGeometry(0.1, 0.3, 0.1),
            new THREE.MeshPhongMaterial({ color: 0x555555 })
        );
        mount.position.y = 2.1;

        this.panel = new THREE.Group();
        this.panel.add(mount);
  
        const panelMaterial =new THREE.MeshPhongMaterial({
                color: 0x1a2f5a,
                shininess: 100,
            });
        var texture = new THREE.TextureLoader().load('./src/assets/solar_panel_texture.jpeg');
        panelMaterial.map = texture;

        // Solar panel
        const panel = new THREE.Mesh(
            new THREE.BoxGeometry(2, 1.2, 0.05),
            panelMaterial
            
        );

        panel.position.y = 2.4;
        panel.rotation.x = -Math.PI / 6; // 30° tilt
        this.panel.add(panel);
        this.mesh.add(this.panel);

        
    }

    getObject() {
        return this.mesh;
    }
}
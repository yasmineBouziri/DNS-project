
Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"
  config.vm.box_check_update = false

  #-----router-----

  config.vm.define "router" do |machine|
    machine.vm.hostname = "router"
    machine.vm.network "private_network",
      ip: "10.10.10.1",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-clients"

    machine.vm.network "private_network",
      ip: "10.10.20.1",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-dns"

    machine.vm.network "private_network",
      ip: "10.10.30.1",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-supervision"

    machine.vm.provider "virtualbox" do |vb|
      vb.name = "dnslab-router"
      vb.memory = 512
      vb.cpus = 1
    end

    # Enable IPv4 forwarding automatically
    machine.vm.provision "forwarding",
      type: "shell",
      run: "always",
      inline: <<-SHELL
        echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-lab-router.conf
        sysctl --system > /dev/null
        echo "IP forwarding: $(cat /proc/sys/net/ipv4/ip_forward)"
      SHELL
  end

#-----client-----
  config.vm.define "client" do |machine|
    machine.vm.hostname = "client"

    machine.vm.network "private_network",
      ip: "10.10.10.10",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-clients"

    machine.vm.provider "virtualbox" do |vb|
      vb.name = "dnslab-client"
      vb.memory = 512
      vb.cpus = 1
    end
    #automatically add routes
    machine.vm.provision "routes",
      type: "shell",
      run: "always",
      inline: <<-SHELL
        ip route replace 10.10.20.0/24 via 10.10.10.1
        ip route replace 10.10.30.0/24 via 10.10.10.1
        echo "Client routes configured"
      SHELL
  end

#-----Primary DNS-----
  config.vm.define "primary" do |machine|
    machine.vm.hostname = "primary"

    machine.vm.network "private_network",
      ip: "10.10.20.30",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-dns"

    machine.vm.provider "virtualbox" do |vb|
      vb.name = "dnslab-primary"
      vb.memory = 512
      vb.cpus = 1
    end
    #automatically add routes 
    machine.vm.provision "routes",
      type: "shell",
      run: "always",
      inline: <<-SHELL
        ip route replace 10.10.10.0/24 via 10.10.20.1
        ip route replace 10.10.30.0/24 via 10.10.20.1
        echo "Primary routes configured"
      SHELL
  end

#-----Secondary DNS-----
  config.vm.define "secondary" do |machine|
    machine.vm.hostname = "secondary"

    machine.vm.network "private_network",
      ip: "10.10.20.31",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-dns"

    machine.vm.provider "virtualbox" do |vb|
      vb.name = "dnslab-secondary"
      vb.memory = 512
      vb.cpus = 1
    end

    machine.vm.provision "routes",
      type: "shell",
      run: "always",
      inline: <<-SHELL
        ip route replace 10.10.10.0/24 via 10.10.20.1
        ip route replace 10.10.30.0/24 via 10.10.20.1
        echo "Secondary routes configured"
      SHELL
  end

 #-----resolver-----
  config.vm.define "resolver" do |machine|
    machine.vm.hostname = "resolver"

    machine.vm.network "private_network",
      ip: "10.10.10.20",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-clients"

    machine.vm.provider "virtualbox" do |vb|
      vb.name = "dnslab-resolver"
      vb.memory = 1024
      vb.cpus = 1
    end

    machine.vm.provision "routes",
      type: "shell",
      run: "always",
      inline: <<-SHELL
        ip route replace 10.10.20.0/24 via 10.10.10.1
        ip route replace 10.10.30.0/24 via 10.10.10.1
        echo "Resolver routes configured"
      SHELL
  end

#-----supervision-----
  config.vm.define "supervision" do |machine|
    machine.vm.hostname = "supervision"

    machine.vm.network "private_network",
      ip: "10.10.30.50",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-supervision"

    machine.vm.provider "virtualbox" do |vb|
      vb.name = "dnslab-supervision"
      vb.memory = 1536
      vb.cpus = 1
    end

    machine.vm.provision "routes",
      type: "shell",
      run: "always",
      inline: <<-SHELL
        ip route replace 10.10.10.0/24 via 10.10.30.1
        ip route replace 10.10.20.0/24 via 10.10.30.1
        echo "Supervision routes configured"
      SHELL
  end
#-----attacker-----
  config.vm.define "attacker", autostart: false do |machine|
    machine.vm.hostname = "attacker"

    machine.vm.network "private_network",
      ip: "10.10.10.40",
      netmask: "255.255.255.0",
      virtualbox__intnet: "zone-clients"

    machine.vm.provider "virtualbox" do |vb|
      vb.name = "dnslab-attacker"
      vb.memory = 512
      vb.cpus = 1
    end

    machine.vm.provision "routes",
      type: "shell",
      run: "always",
      inline: <<-SHELL
        ip route replace 10.10.20.0/24 via 10.10.10.1
        ip route replace 10.10.30.0/24 via 10.10.10.1
        echo "Attacker routes configured"
      SHELL
  end 
end


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

#-----DNS-----
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

end

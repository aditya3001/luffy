import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, theme, Button, Dropdown, Space, Badge, Select, Alert, Modal, Form, Input, message } from 'antd';
import {
  DashboardOutlined,
  ClusterOutlined,
  ToolOutlined,
  DatabaseOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BellOutlined,
  UserOutlined,
  CloseOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '@/store';
import { useServiceContext } from '@/contexts/ServiceContext';
import { servicesAPI } from '@/api/client';

const { Header, Sider, Content } = Layout;

const AppLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  
  const { sidebarCollapsed, setSidebarCollapsed } = useAppStore();
  const { selectedService, setSelectedService } = useServiceContext();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm();
  const queryClient = useQueryClient();

  // Fetch services for the dropdown
  const { data: services = [] } = useQuery({
    queryKey: ['services'],
    queryFn: servicesAPI.list,
  });

  // Create service mutation
  const createServiceMutation = useMutation({
    mutationFn: (values: any) => servicesAPI.create({
      id: values.id,
      name: values.name,
      description: values.description,
      is_active: true,
    }),
    onSuccess: (newService) => {
      message.success(`Service "${newService.name}" created successfully!`);
      setIsCreateModalOpen(false);
      createForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['services'] });
      setSelectedService(newService.id);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to create service');
    },
  });

  const menuItems: MenuProps['items'] = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
      onClick: () => navigate('/dashboard'),
    },
    {
      key: '/clusters',
      icon: <ClusterOutlined />,
      label: 'Exception Clusters',
      onClick: () => navigate('/clusters'),
    },
    {
      key: '/tasks',
      icon: <ToolOutlined />,
      label: 'Task Management',
      onClick: () => navigate('/tasks'),
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: 'Settings',
      onClick: () => navigate('/settings'),
    },
  ];

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      label: 'Profile',
    },
    {
      key: 'preferences',
      label: 'Preferences',
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      label: 'Logout',
      danger: true,
    },
  ];

  const selectedKey = menuItems.find((item) =>
    location.pathname.startsWith(item!.key as string)
  )?.key as string || '/dashboard';

  return (
    <Layout style={{ minHeight: '100vh', maxWidth: '100vw', overflowX: 'hidden' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={sidebarCollapsed}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: sidebarCollapsed ? 20 : 24,
            fontWeight: 'bold',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          }}
        >
          {sidebarCollapsed ? '🏴‍☠️' : '🏴‍☠️ Luffy'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          style={{ marginTop: 8 }}
        />
      </Sider>

      <Layout style={{ 
        marginLeft: sidebarCollapsed ? 80 : 200, 
        transition: 'all 0.2s',
        maxWidth: '100%',
        overflowX: 'hidden'
      }}>
        <Header
          style={{
            padding: '0 24px',
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid #f0f0f0',
            position: 'sticky',
            top: 0,
            zIndex: 99,
            maxWidth: '100%',
          }}
        >
          <Space>
            <Button
              type="text"
              icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              style={{
                fontSize: '16px',
                width: 48,
                height: 48,
              }}
            />

            {/* Service Selection */}
            <Space>
              <span style={{ fontWeight: 500, color: token.colorTextSecondary }}>Service:</span>
              <Select
                placeholder="Select a service"
                value={selectedService}
                onChange={setSelectedService}
                style={{ minWidth: 200 }}
                allowClear
                showSearch
                filterOption={(input, option) =>
                  (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
                }
                options={[
                  { value: undefined, label: 'All Services' },
                  ...services.map(service => ({
                    value: service.id,
                    label: service.name,
                  }))
                ]}
              />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setIsCreateModalOpen(true)}
              >
                New Service
              </Button>
            </Space>
          </Space>

          <Space size="large">
            <Badge count={3} size="small">
              <Button
                type="text"
                icon={<BellOutlined style={{ fontSize: 18 }} />}
                size="large"
              />
            </Badge>

            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button
                type="text"
                icon={<UserOutlined style={{ fontSize: 18 }} />}
                size="large"
              >
                Admin
              </Button>
            </Dropdown>
          </Space>
        </Header>

        <Content
          style={{
            margin: '24px',
            padding: 24,
            minHeight: 280,
            background: token.colorBgContainer,
            borderRadius: token.borderRadiusLG,
            maxWidth: '100%',
            overflowX: 'hidden',
          }}
        >
          {/* Service Selection Alert */}
          {selectedService && (
            <Alert
              message={`Viewing data for: ${services.find(s => s.id === selectedService)?.name || selectedService}`}
              type="info"
              showIcon
              closable
              onClose={() => setSelectedService(undefined)}
              style={{ marginBottom: 24 }}
              action={
                <Button
                  size="small"
                  type="text"
                  icon={<CloseOutlined />}
                  onClick={() => setSelectedService(undefined)}
                >
                  Clear Filter
                </Button>
              }
            />
          )}
          <Outlet />
        </Content>
      </Layout>

      {/* Create Service Modal */}
      <Modal
        title="Create New Service"
        open={isCreateModalOpen}
        onCancel={() => {
          setIsCreateModalOpen(false);
          createForm.resetFields();
        }}
        onOk={() => createForm.submit()}
        okText="Create Service"
        confirmLoading={createServiceMutation.isPending}
        width={600}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={(values) => createServiceMutation.mutate(values)}
        >
          <Form.Item
            name="id"
            label="Service ID"
            rules={[
              { required: true, message: 'Please enter service ID' },
              { pattern: /^[a-z0-9-]+$/, message: 'Only lowercase letters, numbers, and hyphens allowed' }
            ]}
            extra="Unique identifier (e.g., web-app, api-service)"
          >
            <Input placeholder="web-app" />
          </Form.Item>

          <Form.Item
            name="name"
            label="Service Name"
            rules={[{ required: true, message: 'Please enter service name' }]}
          >
            <Input placeholder="Web Application" />
          </Form.Item>

          <Form.Item
            name="description"
            label="Description"
          >
            <Input.TextArea
              placeholder="Brief description of the service"
              rows={3}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  );
};

export default AppLayout;

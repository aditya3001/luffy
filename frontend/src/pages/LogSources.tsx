import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  message,
  Popconfirm,
  Badge,
  Tooltip,
  Tabs,
  Row,
  Col,
  Statistic,
  Divider,
  Typography,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  ApiOutlined,
  SettingOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { servicesAPI, taskManagementAPI, logSourceAPI } from '@/api/client';
import { useServiceContext } from '@/contexts/ServiceContext';

const { TabPane } = Tabs;
const { Title, Text } = Typography;

const LogSources = () => {
  const { selectedService, setSelectedService } = useServiceContext();
  const [isServiceModalOpen, setIsServiceModalOpen] = useState(false);
  const [isLogSourceModalOpen, setIsLogSourceModalOpen] = useState(false);
  const [editingService, setEditingService] = useState<any>(null);
  const [editingLogSource, setEditingLogSource] = useState<any>(null);
  const [serviceForm] = Form.useForm();
  const [logSourceForm] = Form.useForm();
  const queryClient = useQueryClient();

  // Fetch services for reference
  const { data: services = [], isLoading: servicesLoading } = useQuery({
    queryKey: ['services'],
    queryFn: servicesAPI.list,
  });

  // Fetch log sources for selected service only
  const { data: logSources = [], isLoading: logSourcesLoading } = useQuery({
    queryKey: ['log-sources', selectedService],
    queryFn: () => selectedService ? servicesAPI.listLogSources(selectedService) : Promise.resolve([]),
    enabled: !!selectedService,
  });

  // Fetch service-specific task management overview
  const { data: taskOverview } = useQuery({
    queryKey: ['task-overview', selectedService],
    queryFn: () => selectedService ? taskManagementAPI.getServiceTasks(selectedService) : Promise.resolve(null),
    enabled: !!selectedService,
  });

  // Service mutations
  const createServiceMutation = useMutation({
    mutationFn: servicesAPI.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      setIsServiceModalOpen(false);
      serviceForm.resetFields();
      message.success('Service created successfully');
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to create service');
    },
  });

  const updateServiceMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => servicesAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      setIsServiceModalOpen(false);
      serviceForm.resetFields();
      setEditingService(null);
      message.success('Service updated successfully');
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to update service');
    },
  });

  const deleteServiceMutation = useMutation({
    mutationFn: servicesAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      message.success('Service deleted successfully');
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to delete service');
    },
  });

  // Log source mutations
  const createLogSourceMutation = useMutation({
    mutationFn: (data: any) => logSourceAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['log-sources'] });
      queryClient.invalidateQueries({ queryKey: ['log-sources', selectedService] });
      setIsLogSourceModalOpen(false);
      logSourceForm.resetFields();
      message.success('Log source created successfully');
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to create log source');
    },
  });

  const updateLogSourceMutation = useMutation({
    mutationFn: ({ logSourceId, data }: { logSourceId: string; data: any }) => 
      logSourceAPI.update(logSourceId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['log-sources'] });
      queryClient.invalidateQueries({ queryKey: ['log-sources', selectedService] });
      setIsLogSourceModalOpen(false);
      logSourceForm.resetFields();
      setEditingLogSource(null);
      message.success('Log source updated successfully');
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to update log source');
    },
  });

  const deleteLogSourceMutation = useMutation({
    mutationFn: (logSourceId: string) => logSourceAPI.delete(logSourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['log-sources'] });
      queryClient.invalidateQueries({ queryKey: ['log-sources', selectedService] });
      message.success('Log source deleted successfully');
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to delete log source');
    },
  });

  const testConnectionMutation = useMutation({
    mutationFn: (logSourceId: string) => logSourceAPI.test(logSourceId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['log-sources'] });
      queryClient.invalidateQueries({ queryKey: ['log-sources', selectedService] });
      if (data.success) {
        message.success(`Connection test successful (${data.response_time_ms}ms)`);
      } else {
        message.error(`Connection test failed: ${data.message}`);
      }
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to test connection');
    },
  });

  const toggleLogSourceMutation = useMutation({
    mutationFn: ({ logSourceId, enabled }: { logSourceId: string; enabled: boolean }) => 
      logSourceAPI.controlMonitoring(logSourceId, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['log-sources'] });
      queryClient.invalidateQueries({ queryKey: ['log-sources', selectedService] });
      queryClient.invalidateQueries({ queryKey: ['monitoring-status'] });
      message.success('Log source monitoring toggled successfully');
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to toggle log source monitoring');
    },
  });

  // Event handlers
  const handleEditService = (service: any) => {
    setEditingService(service);
    serviceForm.setFieldsValue(service);
    setIsServiceModalOpen(true);
  };

  const handleCreateLogSource = () => {
    if (!selectedService) {
      message.warning('Please select a service first');
      return;
    }
    setEditingLogSource(null);
    logSourceForm.resetFields();
    setIsLogSourceModalOpen(true);
  };

  const handleEditLogSource = (logSource: any) => {
    setEditingLogSource(logSource);
    logSourceForm.setFieldsValue(logSource);
    setIsLogSourceModalOpen(true);
  };

  const handleServiceSubmit = async () => {
    try {
      const values = await serviceForm.validateFields();
      if (editingService) {
        updateServiceMutation.mutate({ id: editingService.id, data: values });
      } else {
        createServiceMutation.mutate(values);
      }
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  const handleLogSourceSubmit = async () => {
    try {
      const values = await logSourceForm.validateFields();
      if (editingLogSource) {
        updateLogSourceMutation.mutate({ 
          logSourceId: editingLogSource.id, 
          data: values 
        });
      } else {
        createLogSourceMutation.mutate({ ...values, service_id: selectedService! });
      }
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  // Table columns for services
  const serviceColumns: ColumnsType<any> = [
    {
      title: 'Service Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Space>
          <ApiOutlined />
          <strong>{text}</strong>
        </Space>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => text || <Text type="secondary">No description</Text>,
    },
    {
      title: 'Log Sources',
      dataIndex: 'log_sources_count',
      key: 'log_sources_count',
      render: (count: number) => (
        <Badge count={count} style={{ backgroundColor: '#52c41a' }} />
      ),
    },
    {
      title: 'Active Exceptions',
      dataIndex: 'active_exceptions_count',
      key: 'active_exceptions_count',
      render: (count: number) => (
        <Badge 
          count={count} 
          style={{ backgroundColor: count > 0 ? '#ff4d4f' : '#52c41a' }} 
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record: any) => (
        <Space>
          <Button
            type="primary"
            size="small"
            onClick={() => setSelectedService(record.id)}
          >
            View Sources
          </Button>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => handleEditService(record)}
          />
          <Popconfirm
            title="Delete service?"
            description="This will delete the service and all its log sources."
            onConfirm={() => deleteServiceMutation.mutate(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button
              icon={<DeleteOutlined />}
              size="small"
              danger
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // Table columns for log sources
  const logSourceColumns: ColumnsType<any> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Space>
          <DatabaseOutlined />
          <strong>{text}</strong>
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'source_type',
      key: 'source_type',
      render: (type: string) => (
        <Tag color="blue">{type.toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Host',
      dataIndex: 'host',
      key: 'host',
      render: (host: string, record: any) => `${host}:${record.port}`,
    },
    {
      title: 'Index Pattern',
      dataIndex: 'index_pattern',
      key: 'index_pattern',
      render: (pattern: string) => (
        <code style={{ backgroundColor: '#f5f5f5', padding: '2px 4px' }}>{pattern}</code>
      ),
    },
    {
      title: 'Connection',
      dataIndex: 'connection_status',
      key: 'connection_status',
      render: (status: string) => {
        const statusConfig = {
          connected: { color: 'success', icon: <CheckCircleOutlined /> },
          disconnected: { color: 'default', icon: <CloseCircleOutlined /> },
          error: { color: 'error', icon: <CloseCircleOutlined /> },
          unknown: { color: 'warning', icon: <CloseCircleOutlined /> },
        };
        const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.unknown;
        return (
          <Badge status={config.color as any} text={status} />
        );
      },
    },
    {
      title: 'Fetch Enabled',
      dataIndex: 'fetch_enabled',
      key: 'fetch_enabled',
      render: (enabled: boolean, record: any) => (
        <Switch
          checked={enabled}
          onChange={(checked) => toggleLogSourceMutation.mutate({
            logSourceId: record.id,
            enabled: checked
          })}
          checkedChildren={<PlayCircleOutlined />}
          unCheckedChildren={<PauseCircleOutlined />}
        />
      ),
    },
    {
      title: 'Active Exceptions',
      dataIndex: 'active_exceptions_count',
      key: 'active_exceptions_count',
      render: (count: number) => (
        <Badge 
          count={count} 
          style={{ backgroundColor: count > 0 ? '#ff4d4f' : '#52c41a' }} 
        />
      ),
    },
    {
      title: 'Code Indexing',
      key: 'code_indexing',
      render: (_, record: any) => {
        if (!record.code_indexing_enabled) {
          return <Tag>Disabled</Tag>;
        }
        
        const statusConfig: Record<string, { color: string; icon: any; text: string }> = {
          valid: { color: 'success', icon: <CheckCircleOutlined />, text: 'Active' },
          expired: { color: 'error', icon: <CloseCircleOutlined />, text: 'Token Expired' },
          invalid: { color: 'error', icon: <CloseCircleOutlined />, text: 'Invalid Token' },
          not_configured: { color: 'default', icon: <CloseCircleOutlined />, text: 'Not Configured' },
        };
        
        const config = statusConfig[record.token_status || 'not_configured'];
        
        return (
          <Tooltip title={record.indexing_error || 'Code indexing status'}>
            <Tag color={config.color} icon={config.icon}>
              {config.text}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record: any) => (
        <Space>
          <Tooltip title="Test Connection">
            <Button
              icon={<ThunderboltOutlined />}
              size="small"
              onClick={() => testConnectionMutation.mutate(record.id)}
              loading={testConnectionMutation.isPending}
            />
          </Tooltip>
          {record.code_indexing_enabled && (
            <Tooltip title="Trigger Code Indexing">
              <Button
                icon={<SyncOutlined />}
                size="small"
                onClick={() => {
                  Modal.confirm({
                    title: 'Trigger Code Indexing',
                    content: `This will trigger code indexing for "${record.name}". Continue?`,
                    onOk: () => {
                      logSourceAPI.triggerIndexing(record.id, false)
                        .then((data) => {
                          message.success(`Code indexing triggered! Task ID: ${data.task_id}`);
                          queryClient.invalidateQueries({ queryKey: ['log-sources'] });
                        })
                        .catch((error) => {
                          message.error(error.response?.data?.detail || 'Failed to trigger indexing');
                        });
                    },
                  });
                }}
              />
            </Tooltip>
          )}
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => handleEditLogSource(record)}
          />
          <Popconfirm
            title="Delete log source?"
            description="This will delete the log source and stop log fetching."
            onConfirm={() => deleteLogSourceMutation.mutate(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button
              icon={<DeleteOutlined />}
              size="small"
              danger
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const selectedServiceData = services.find(s => s.id === selectedService);

  return (
    <div style={{ padding: 24, maxWidth: '100%', overflowX: 'hidden' }}>
      {/* Header with Actions */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <Title level={2} style={{ marginBottom: 8 }}>
            <ApiOutlined /> Services & Log Sources
          </Title>
          <Text type="secondary">
            {selectedService 
              ? `Managing log sources for ${selectedServiceData?.name || 'selected service'}` 
              : 'Create services and configure their log sources for exception monitoring'}
          </Text>
        </div>
        {selectedService && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size="large"
            onClick={handleCreateLogSource}
          >
            Add Log Source
          </Button>
        )}
      </div>

      {!selectedService ? (
        // Show service selection prompt when no service is selected
        <Card>
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <DatabaseOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 24 }} />
            <Title level={3} style={{ marginBottom: 16 }}>Select a Service</Title>
            <Text type="secondary" style={{ fontSize: 16, display: 'block', marginBottom: 32 }}>
              Select a service from the header dropdown to view and manage its log sources.<br />
              Use the "New Service" button in the header to create a new service.
            </Text>
          </div>

          {/* Services Overview Table */}
          {services.length > 0 && (
            <div style={{ marginTop: 48 }}>
              <Divider />
              <Title level={4} style={{ marginBottom: 16 }}>
                <ApiOutlined /> All Services
              </Title>
              <Table
                columns={serviceColumns}
                dataSource={services}
                rowKey="id"
                loading={servicesLoading}
                pagination={{ pageSize: 10 }}
              />
            </div>
          )}
        </Card>
      ) : (
        <>
          {/* Overview Statistics */}
          {taskOverview && (
            <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Total Services"
                    value={taskOverview.total_services}
                    prefix={<ApiOutlined />}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Active Services"
                    value={taskOverview.active_services}
                    prefix={<PlayCircleOutlined />}
                    valueStyle={{ color: '#3f8600' }}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Total Log Sources"
                    value={taskOverview.total_log_sources}
                    prefix={<DatabaseOutlined />}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic
                    title="Active Log Sources"
                    value={taskOverview.active_log_sources}
                    prefix={<ThunderboltOutlined />}
                    valueStyle={{ color: '#3f8600' }}
                  />
                </Card>
              </Col>
            </Row>
          )}

          {/* Service Info Card */}
          <Card style={{ marginBottom: 24, background: '#fafafa' }}>
            <Row align="middle">
              <Col flex="auto">
                <Space direction="vertical" size={0}>
                  <Text type="secondary">Currently Managing</Text>
                  <Title level={4} style={{ margin: 0 }}>
                    <ApiOutlined /> {selectedServiceData?.name}
                  </Title>
                  {selectedServiceData?.description && (
                    <Text type="secondary">{selectedServiceData.description}</Text>
                  )}
                </Space>
              </Col>
              <Col>
                <Space>
                  <Button
                    icon={<EditOutlined />}
                    onClick={() => handleEditService(selectedServiceData)}
                  >
                    Edit Service
                  </Button>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={handleCreateLogSource}
                  >
                    Add Log Source
                  </Button>
                  <Button
                    onClick={() => setSelectedService(undefined)}
                  >
                    View All Services
                  </Button>
                </Space>
              </Col>
            </Row>
          </Card>

          {/* Log Sources Table */}
          <Card
            title={
              <Space>
                <DatabaseOutlined />
                <span>Log Sources ({logSources.length})</span>
              </Space>
            }
            extra={
              logSources.length === 0 && (
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={handleCreateLogSource}
                >
                  Add Your First Log Source
                </Button>
              )
            }
          >
            {logSources.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                <DatabaseOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
                <Title level={4} style={{ color: '#8c8c8c', marginBottom: 8 }}>
                  No Log Sources Configured
                </Title>
                <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
                  Add a log source to start monitoring exceptions from OpenSearch, Elasticsearch, or other sources.
                </Text>
                <Button
                  type="primary"
                  size="large"
                  icon={<PlusOutlined />}
                  onClick={handleCreateLogSource}
                >
                  Add Log Source
                </Button>
              </div>
            ) : (
              <Table
                columns={logSourceColumns}
                dataSource={logSources}
                rowKey="id"
                loading={logSourcesLoading}
                pagination={{ pageSize: 10 }}
              />
            )}
          </Card>
        </>
      )}

      {/* Service Modal */}
      <Modal
        title={editingService ? 'Edit Service' : 'Create Service'}
        open={isServiceModalOpen}
        onOk={handleServiceSubmit}
        onCancel={() => {
          setIsServiceModalOpen(false);
          serviceForm.resetFields();
          setEditingService(null);
        }}
        confirmLoading={createServiceMutation.isPending || updateServiceMutation.isPending}
      >
        <Form form={serviceForm} layout="vertical">
          <Form.Item
            name="name"
            label="Service Name"
            rules={[{ required: true, message: 'Please enter service name' }]}
          >
            <Input placeholder="e.g., User Service" />
          </Form.Item>
          <Form.Item
            name="description"
            label="Description"
          >
            <Input.TextArea placeholder="Service description" rows={3} />
          </Form.Item>
          <Form.Item
            name="version"
            label="Version"
          >
            <Input placeholder="e.g., 1.0.0" />
          </Form.Item>
          <Form.Item
            name="repository_url"
            label="Repository URL"
          >
            <Input placeholder="https://github.com/..." />
          </Form.Item>
        </Form>
      </Modal>

      {/* Log Source Modal */}
      <Modal
        title={editingLogSource ? 'Edit Log Source' : 'Create Log Source'}
        open={isLogSourceModalOpen}
        onOk={handleLogSourceSubmit}
        onCancel={() => {
          setIsLogSourceModalOpen(false);
          logSourceForm.resetFields();
          setEditingLogSource(null);
        }}
        confirmLoading={createLogSourceMutation.isPending || updateLogSourceMutation.isPending}
        width={600}
      >
        <Form form={logSourceForm} layout="vertical">
          <Form.Item
            name="name"
            label="Log Source Name"
            rules={[{ required: true, message: 'Please enter log source name' }]}
          >
            <Input placeholder="e.g., Production Logs" />
          </Form.Item>
          
          <Form.Item
            name="source_type"
            label="Source Type"
            rules={[{ required: true, message: 'Please select source type' }]}
          >
            <Select placeholder="Select source type">
              <Select.Option value="opensearch">OpenSearch</Select.Option>
              <Select.Option value="elasticsearch">Elasticsearch</Select.Option>
              <Select.Option value="loki">Loki</Select.Option>
              <Select.Option value="cloudwatch">CloudWatch</Select.Option>
              <Select.Option value="splunk">Splunk</Select.Option>
            </Select>
          </Form.Item>

          <Row gutter={16}>
            <Col span={16}>
              <Form.Item
                name="host"
                label="Host"
                rules={[{ required: true, message: 'Please enter host' }]}
              >
                <Input placeholder="localhost" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="port"
                label="Port"
                rules={[{ required: true, message: 'Please enter port' }]}
              >
                <Input placeholder="9200" type="number" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="username" label="Username">
                <Input placeholder="Username (optional)" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="password" label="Password">
                <Input.Password placeholder="Password (optional)" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="index_pattern"
            label="Index Pattern"
            rules={[{ required: true, message: 'Please enter index pattern' }]}
          >
            <Input placeholder="logs-*" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="use_ssl" label="Use SSL" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="verify_certs" label="Verify Certificates" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="fetch_interval_minutes"
            label="Fetch Interval (minutes)"
            rules={[{ required: true, message: 'Please enter fetch interval' }]}
          >
            <Input placeholder="30" type="number" min={1} max={1440} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default LogSources;

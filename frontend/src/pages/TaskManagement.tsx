import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Switch,
  Button,
  Space,
  Typography,
  Row,
  Col,
  Statistic,
  Tag,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  message,
  Alert,
  Table,
  Divider,
  Tabs,
  Badge,
  Tooltip,
  Collapse,
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  SettingOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  EditOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  ControlOutlined,
} from '@ant-design/icons';
import { format } from 'date-fns';
import { taskManagementAPI, servicesAPI } from '@/api/client';
import type { ColumnsType } from 'antd/es/table';
import { useServiceContext } from '@/contexts/ServiceContext';

const { Title, Text } = Typography;
const { TabPane } = Tabs;
const { Panel } = Collapse;

const TaskManagement = () => {
  const [isServiceConfigModalOpen, setIsServiceConfigModalOpen] = useState(false);
  const [isLogSourceConfigModalOpen, setIsLogSourceConfigModalOpen] = useState(false);
  const [editingLogSourceId, setEditingLogSourceId] = useState<string | null>(null);
  const [editingTask, setEditingTask] = useState<string | null>(null);
  const [durationUnit, setDurationUnit] = useState<'minutes' | 'hours' | 'days'>('minutes');
  const [durationValue, setDurationValue] = useState<number>(30);
  const [serviceConfigForm] = Form.useForm();
  const [logSourceConfigForm] = Form.useForm();
  const queryClient = useQueryClient();
  const { selectedService } = useServiceContext();

  // Fetch service-specific task configuration
  const { data: serviceTasksData, isLoading: serviceTasksLoading } = useQuery({
    queryKey: ['service-tasks', selectedService],
    queryFn: () => selectedService ? taskManagementAPI.getServiceTasks(selectedService) : Promise.resolve(null),
    enabled: !!selectedService,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Fetch log sources for the selected service
  const { data: logSources = [], isLoading: logSourcesLoading } = useQuery({
    queryKey: ['log-sources', selectedService],
    queryFn: () => selectedService ? servicesAPI.listLogSources(selectedService) : Promise.resolve([]),
    enabled: !!selectedService,
  });

  // Fetch log source tasks
  const { data: logSourceTasksData, isLoading: logSourceTasksLoading } = useQuery({
    queryKey: ['log-source-tasks', selectedService],
    queryFn: () => selectedService ? taskManagementAPI.listLogSourceTasks(selectedService) : Promise.resolve([]),
    enabled: !!selectedService,
  });

  // Service-level mutations
  const updateServiceTasksMutation = useMutation({
    mutationFn: ({ serviceId, config }: { serviceId: string; config: any }) =>
      taskManagementAPI.updateServiceTasks(serviceId, config),
    onSuccess: () => {
      message.success('Service task configuration updated successfully');
      queryClient.invalidateQueries({ queryKey: ['service-tasks', selectedService] });
      setIsServiceConfigModalOpen(false);
      serviceConfigForm.resetFields();
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to update service task configuration');
    },
  });

  const enableAllServiceTasksMutation = useMutation({
    mutationFn: (serviceId: string) => taskManagementAPI.enableAllServiceTasks(serviceId),
    onSuccess: () => {
      message.success('All service tasks enabled successfully');
      queryClient.invalidateQueries({ queryKey: ['service-tasks', selectedService] });
      queryClient.invalidateQueries({ queryKey: ['log-source-tasks', selectedService] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to enable all service tasks');
    },
  });

  const disableAllServiceTasksMutation = useMutation({
    mutationFn: (serviceId: string) => taskManagementAPI.disableAllServiceTasks(serviceId),
    onSuccess: () => {
      message.success('All service tasks disabled successfully');
      queryClient.invalidateQueries({ queryKey: ['service-tasks', selectedService] });
      queryClient.invalidateQueries({ queryKey: ['log-source-tasks', selectedService] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to disable all service tasks');
    },
  });

  // Log source-level mutations
  const updateLogSourceTasksMutation = useMutation({
    mutationFn: ({ logSourceId, config }: { logSourceId: string; config: any }) =>
      taskManagementAPI.updateLogSourceTasks(logSourceId, config),
    onSuccess: () => {
      message.success('Log source task configuration updated successfully');
      queryClient.invalidateQueries({ queryKey: ['log-source-tasks', selectedService] });
      setIsLogSourceConfigModalOpen(false);
      logSourceConfigForm.resetFields();
      setEditingLogSourceId(null);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to update log source task configuration');
    },
  });

  const toggleLogSourceFetchMutation = useMutation({
    mutationFn: ({ logSourceId, enabled }: { logSourceId: string; enabled: boolean }) =>
      taskManagementAPI.toggleLogSourceFetch(logSourceId, enabled),
    onSuccess: () => {
      message.success('Log source monitoring toggled successfully');
      queryClient.invalidateQueries({ queryKey: ['log-source-tasks', selectedService] });
      queryClient.invalidateQueries({ queryKey: ['log-sources', selectedService] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to toggle log source monitoring');
    },
  });

  // Manual trigger mutations
  const triggerLogFetchMutation = useMutation({
    mutationFn: (serviceId: string) => servicesAPI.triggerLogFetch(serviceId),
    onSuccess: (data) => {
      message.success(`Log fetch triggered successfully! Task ID: ${data.task_id}`);
      queryClient.invalidateQueries({ queryKey: ['service-tasks', selectedService] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to trigger log fetch');
    },
  });

  const triggerCodeIndexingMutation = useMutation({
    mutationFn: (serviceId: string) => servicesAPI.triggerCodeIndexing(serviceId),
    onSuccess: (data) => {
      message.success(`Code indexing triggered successfully! Task ID: ${data.task_id}`);
      queryClient.invalidateQueries({ queryKey: ['service-tasks', selectedService] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to trigger code indexing');
    },
  });

  // Event  // Handlers for inline editing
  const handleTaskUpdate = (field: string, value: any) => {
    if (selectedService) {
      const updates: any = { [field]: value };
      updateServiceTasksMutation.mutate({
        serviceId: selectedService,
        config: updates,
      });
    }
  };

  // Helper to get current duration value based on selected unit
  const getCurrentDuration = () => {
    if (!serviceTasksData) return 30;
    
    if (durationUnit === 'days') {
      return serviceTasksData.log_fetch_duration_days || 1;
    } else if (durationUnit === 'hours') {
      return serviceTasksData.log_fetch_duration_hours || 1;
    } else {
      return serviceTasksData.log_fetch_duration_minutes || 30;
    }
  };

  // Helper to get display text for duration
  const getDurationDisplayText = () => {
    if (!serviceTasksData) return '30 minutes';
    
    if (serviceTasksData.log_fetch_duration_days) {
      return `${serviceTasksData.log_fetch_duration_days} day${serviceTasksData.log_fetch_duration_days > 1 ? 's' : ''}`;
    } else if (serviceTasksData.log_fetch_duration_hours) {
      return `${serviceTasksData.log_fetch_duration_hours} hour${serviceTasksData.log_fetch_duration_hours > 1 ? 's' : ''}`;
    } else {
      return `${serviceTasksData.log_fetch_duration_minutes || 30} minute${(serviceTasksData.log_fetch_duration_minutes || 30) > 1 ? 's' : ''}`;
    }
  };

  // Helper to save duration to database
  const handleSaveDuration = () => {
    if (!selectedService || !durationValue) return;
    
    const updates: any = {
      log_fetch_duration_minutes: null,
      log_fetch_duration_hours: null,
      log_fetch_duration_days: null,
    };
    
    if (durationUnit === 'days') {
      updates.log_fetch_duration_days = durationValue;
    } else if (durationUnit === 'hours') {
      updates.log_fetch_duration_hours = durationValue;
    } else {
      updates.log_fetch_duration_minutes = durationValue;
    }
    
    updateServiceTasksMutation.mutate({
      serviceId: selectedService,
      config: updates,
    });
    setEditingTask(null);
  };

  // Initialize duration value when editing starts
  const handleStartEditDuration = () => {
    if (serviceTasksData) {
      if (serviceTasksData.log_fetch_duration_days) {
        setDurationUnit('days');
        setDurationValue(serviceTasksData.log_fetch_duration_days);
      } else if (serviceTasksData.log_fetch_duration_hours) {
        setDurationUnit('hours');
        setDurationValue(serviceTasksData.log_fetch_duration_hours);
      } else {
        setDurationUnit('minutes');
        setDurationValue(serviceTasksData.log_fetch_duration_minutes || 30);
      }
    }
    setEditingTask('log_fetch');
  };

  const handleEditLogSourceConfig = (logSourceId: string) => {
    const logSourceTask = logSourceTasksData?.find((task: any) => task.log_source_id === logSourceId);
    if (logSourceTask) {
      logSourceConfigForm.setFieldsValue({
        fetch_interval_minutes: logSourceTask.fetch_interval_minutes,
        fetch_enabled: logSourceTask.fetch_enabled,
      });
    }
    setEditingLogSourceId(logSourceId);
    setIsLogSourceConfigModalOpen(true);
  };

  const handleLogSourceConfigSubmit = async () => {
    try {
      const values = await logSourceConfigForm.validateFields();
      if (editingLogSourceId) {
        updateLogSourceTasksMutation.mutate({ logSourceId: editingLogSourceId, config: values });
      }
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  // Log source table columns
  const logSourceColumns: ColumnsType<any> = [
    {
      title: 'Log Source',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Space>
          <DatabaseOutlined />
          <strong>{text}</strong>
          <Tag color={record.source_type === 'opensearch' ? 'blue' : 'green'}>
            {record.source_type}
          </Tag>
        </Space>
      ),
    },
    {
      title: 'Fetch Interval',
      dataIndex: 'fetch_interval_minutes',
      key: 'fetch_interval',
      render: (minutes: number) => (
        <Space>
          <ClockCircleOutlined />
          <Text>{minutes} minutes</Text>
        </Space>
      ),
    },
    {
      title: 'Monitoring Status',
      dataIndex: 'fetch_enabled',
      key: 'fetch_enabled',
      render: (enabled: boolean, record: any) => (
        <Switch
          checked={enabled}
          checkedChildren={<CheckCircleOutlined />}
          unCheckedChildren={<PauseCircleOutlined />}
          onChange={(checked) => toggleLogSourceFetchMutation.mutate({ 
            logSourceId: record.id, 
            enabled: checked 
          })}
          loading={toggleLogSourceFetchMutation.isPending}
        />
      ),
    },
    {
      title: 'Last Fetch',
      dataIndex: 'last_fetch_at',
      key: 'last_fetch_at',
      render: (date: string) => date ? format(new Date(date), 'MMM dd, HH:mm:ss') : 'Never',
    },
    {
      title: 'Status',
      dataIndex: 'connection_status',
      key: 'connection_status',
      render: (status: string) => {
        const statusConfig = {
          connected: { color: 'success', icon: <CheckCircleOutlined />, text: 'Connected' },
          error: { color: 'error', icon: <ExclamationCircleOutlined />, text: 'Error' },
          unknown: { color: 'default', icon: <ClockCircleOutlined />, text: 'Unknown' },
        };
        const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.unknown;
        return (
          <Badge status={config.color as any} text={
            <Space>
              {config.icon}
              {config.text}
            </Space>
          } />
        );
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record: any) => (
        <Button
          icon={<SettingOutlined />}
          size="small"
          onClick={() => handleEditLogSourceConfig(record)}
        >
          Configure
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, maxWidth: '100%', overflowX: 'hidden' }}>
      {/* Header */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <Title level={2} style={{ marginBottom: 8 }}>
            <ControlOutlined /> Task Management
          </Title>
          <Text type="secondary">
            {selectedService 
              ? 'Configure and monitor background tasks for log processing and code indexing' 
              : 'Select a service to manage its background tasks'}
          </Text>
        </div>
        <Button 
          icon={<ReloadOutlined />} 
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['service-tasks', selectedService] });
            queryClient.invalidateQueries({ queryKey: ['log-source-tasks', selectedService] });
          }}
          disabled={!selectedService}
        >
          Refresh
        </Button>
      </div>

      {!selectedService ? (
        // Show service selection prompt
        <Card>
          <div style={{ textAlign: 'center', padding: '80px 20px' }}>
            <DatabaseOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 24 }} />
            <Title level={3} style={{ marginBottom: 16 }}>Select a Service</Title>
            <Text type="secondary" style={{ fontSize: 16, display: 'block', marginBottom: 24 }}>
              Choose a service from the header dropdown to configure its background tasks,<br />
              log monitoring intervals, and processing schedules.
            </Text>
          </div>
        </Card>
      ) : (
        <>
          {/* Service Overview Statistics */}
          {serviceTasksData && (
            <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={12}>
                <Card>
                  <Statistic
                    title="Log Fetch Duration"
                    value={getDurationDisplayText()}
                    prefix={<ClockCircleOutlined />}
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card>
                  <Statistic
                    title="Code Indexing Status"
                    value={serviceTasksData.last_code_indexing ? 'Configured' : 'Not Set'}
                    prefix={<ApiOutlined />}
                    valueStyle={{ color: serviceTasksData.last_code_indexing ? '#3f8600' : '#cf1322' }}
                  />
                </Card>
              </Col>
            </Row>
          )}

          <Tabs defaultActiveKey="service">
            {/* Service-Level Tasks Tab */}
            <TabPane 
              tab={
                <span>
                  <ApiOutlined />
                  Service-Level Tasks
                </span>
              } 
              key="service"
            >
              <Card
                title="Service Task Configuration"
                extra={
                  <Space>
                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      onClick={() => selectedService && enableAllServiceTasksMutation.mutate(selectedService)}
                      loading={enableAllServiceTasksMutation.isPending}
                    >
                      Enable All
                    </Button>
                    <Button
                      danger
                      icon={<PauseCircleOutlined />}
                      onClick={() => selectedService && disableAllServiceTasksMutation.mutate(selectedService)}
                      loading={disableAllServiceTasksMutation.isPending}
                    >
                      Disable All
                    </Button>
                  </Space>
                }
              >
                {serviceTasksLoading ? (
                  <div style={{ textAlign: 'center', padding: 40 }}>
                    <ReloadOutlined spin style={{ fontSize: 32, color: '#1890ff' }} />
                  </div>
                ) : serviceTasksData ? (
                  <Row gutter={[16, 16]}>
                    {/* Log Fetch Task */}
                    <Col xs={24} md={12}>
                      <Card
                        type="inner"
                        title={
                          <Space>
                            <DatabaseOutlined style={{ color: '#1890ff' }} />
                            <span>Log Fetch & Processing</span>
                          </Space>
                        }
                        extra={
                          editingTask === 'log_fetch' ? (
                            <Space>
                              <Button 
                                size="small" 
                                type="primary"
                                onClick={handleSaveDuration}
                                loading={updateServiceTasksMutation.isPending}
                              >
                                Save
                              </Button>
                              <Button 
                                size="small" 
                                onClick={() => setEditingTask(null)}
                              >
                                Cancel
                              </Button>
                            </Space>
                          ) : (
                            <Button 
                              size="small" 
                              type="link"
                              icon={<EditOutlined />}
                              onClick={handleStartEditDuration}
                            >
                              Edit
                            </Button>
                          )
                        }
                      >
                        <Space direction="vertical" style={{ width: '100%' }} size="middle">
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <Text type="secondary">Search Duration:</Text>
                            {editingTask === 'log_fetch' ? (
                              <Space>
                                <Select
                                  value={durationUnit}
                                  onChange={(newUnit) => {
                                    // Convert duration when changing units
                                    let newValue = durationValue;
                                    if (durationUnit === 'minutes' && newUnit === 'hours') {
                                      newValue = Math.max(1, Math.round(durationValue / 60));
                                    } else if (durationUnit === 'minutes' && newUnit === 'days') {
                                      newValue = Math.max(1, Math.round(durationValue / 1440));
                                    } else if (durationUnit === 'hours' && newUnit === 'minutes') {
                                      newValue = durationValue * 60;
                                    } else if (durationUnit === 'hours' && newUnit === 'days') {
                                      newValue = Math.max(1, Math.round(durationValue / 24));
                                    } else if (durationUnit === 'days' && newUnit === 'minutes') {
                                      newValue = durationValue * 1440;
                                    } else if (durationUnit === 'days' && newUnit === 'hours') {
                                      newValue = durationValue * 24;
                                    }
                                    setDurationUnit(newUnit);
                                    setDurationValue(newValue);
                                  }}
                                  style={{ width: 100 }}
                                >
                                  <Select.Option value="minutes">Minutes</Select.Option>
                                  <Select.Option value="hours">Hours</Select.Option>
                                  <Select.Option value="days">Days</Select.Option>
                                </Select>
                                <InputNumber
                                  min={1}
                                  max={durationUnit === 'minutes' ? 43200 : durationUnit === 'hours' ? 720 : 30}
                                  value={durationValue}
                                  onChange={(value) => setDurationValue(value || 1)}
                                  style={{ width: 80 }}
                                />
                              </Space>
                            ) : (
                              <Text strong>
                                Last {getDurationDisplayText()}
                              </Text>
                            )}
                          </div>
                          <div>
                            <Text type="secondary">Last Run:</Text>
                            <Text style={{ marginLeft: 8 }}>
                              {serviceTasksData.last_log_fetch 
                                ? format(new Date(serviceTasksData.last_log_fetch), 'MMM dd, HH:mm:ss')
                                : 'Never'}
                            </Text>
                          </div>
                          <Alert
                            message={
                              <>
                                <strong>Search Duration:</strong> How far back to search in OpenSearch logs<br/>
                                <strong>Scheduling:</strong> Task runs automatically via Celery Beat (configured in backend)
                              </>
                            }
                            type="info"
                            showIcon
                          />
                          <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            onClick={() => selectedService && triggerLogFetchMutation.mutate(selectedService)}
                            loading={triggerLogFetchMutation.isPending}
                            block
                          >
                            Trigger Now
                          </Button>
                        </Space>
                      </Card>
                    </Col>

                    {/* Code Indexing Task */}
                    <Col xs={24} md={12}>
                      <Card
                        type="inner"
                        title={
                          <Space>
                            <ApiOutlined style={{ color: '#722ed1' }} />
                            <span>Code Repository Indexing</span>
                          </Space>
                        }
                      >
                        <Space direction="vertical" style={{ width: '100%' }} size="middle">
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <Text type="secondary">Status:</Text>
                            <Tag color={serviceTasksData.code_indexing_status === 'completed' ? 'success' : serviceTasksData.code_indexing_status === 'indexing' ? 'processing' : serviceTasksData.code_indexing_status === 'failed' ? 'error' : 'default'}>
                              {serviceTasksData.code_indexing_status || 'Not Indexed'}
                            </Tag>
                          </div>
                          <div>
                            <Text type="secondary">Last Run:</Text>
                            <Text style={{ marginLeft: 8 }}>
                              {serviceTasksData.last_code_indexing 
                                ? format(new Date(serviceTasksData.last_code_indexing), 'MMM dd, HH:mm:ss')
                                : 'Never'}
                            </Text>
                          </div>
                          {serviceTasksData.last_indexed_commit && (
                            <div>
                              <Text type="secondary">Last Commit:</Text>
                              <Text style={{ marginLeft: 8 }} code>
                                {serviceTasksData.last_indexed_commit.substring(0, 8)}
                              </Text>
                            </div>
                          )}
                          <Alert
                            message="Automatic & Manual Code Indexing"
                            description="Code indexing is triggered automatically when exceptions are detected. You can also trigger it manually at any time using the button below."
                            type="info"
                            showIcon
                          />
                          <Button
                            type="primary"
                            icon={<PlayCircleOutlined />}
                            onClick={() => selectedService && triggerCodeIndexingMutation.mutate(selectedService)}
                            loading={triggerCodeIndexingMutation.isPending}
                            block
                          >
                            Trigger Now
                          </Button>
                        </Space>
                      </Card>
                    </Col>
                  </Row>
                ) : (
                  <Alert
                    message="No task configuration found"
                    description="Service task configuration is not available"
                    type="warning"
                    showIcon
                  />
                )}
              </Card>
            </TabPane>

            {/* Log Source Tasks Tab */}
            <TabPane 
              tab={
                <span>
                  <DatabaseOutlined />
                  Log Source Monitoring ({logSources.length})
                </span>
              } 
              key="log-sources"
            >
              <Card
                title="Log Source Monitoring Configuration"
                extra={
                  <Text type="secondary">
                    Configure individual log source fetch intervals and monitoring status
                  </Text>
                }
              >
                {logSourcesLoading || logSourceTasksLoading ? (
                  <div style={{ textAlign: 'center', padding: 40 }}>
                    <ReloadOutlined spin style={{ fontSize: 32, color: '#1890ff' }} />
                  </div>
                ) : logSources.length === 0 ? (
                  <Alert
                    message="No Log Sources Configured"
                    description="Add log sources to this service to enable log monitoring and processing"
                    type="info"
                    showIcon
                  />
                ) : (
                  <Table
                    columns={logSourceColumns}
                    dataSource={logSources}
                    rowKey="id"
                    pagination={{ pageSize: 10 }}
                  />
                )}
              </Card>
            </TabPane>
          </Tabs>
        </>
      )}

      {/* Log Source Config Modal */}
      <Modal
        title="Edit Log Source Task Configuration"
        open={isLogSourceConfigModalOpen}
        onOk={handleLogSourceConfigSubmit}
        onCancel={() => {
          setIsLogSourceConfigModalOpen(false);
          logSourceConfigForm.resetFields();
          setEditingLogSourceId(null);
        }}
        confirmLoading={updateLogSourceTasksMutation.isPending}
      >
        <Form form={logSourceConfigForm} layout="vertical">
          <Form.Item
            name="fetch_enabled"
            label="Monitoring Status"
            valuePropName="checked"
          >
            <Switch checkedChildren="Enabled" unCheckedChildren="Disabled" />
          </Form.Item>

          <Form.Item
            name="fetch_interval_minutes"
            label="Fetch Interval (minutes)"
            rules={[{ required: true, message: 'Please enter fetch interval' }]}
          >
            <InputNumber min={1} max={1440} style={{ width: '100%' }} />
          </Form.Item>

          <Alert
            message="Note"
            description="Changes will take effect on the next scheduled run. Individual log source intervals override service-level settings."
            type="info"
            showIcon
            style={{ marginTop: 16 }}
          />
        </Form>
      </Modal>
    </div>
  );
};

export default TaskManagement;

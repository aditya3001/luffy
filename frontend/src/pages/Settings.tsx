import { Card, Form, Input, Switch, Button, Space, message, Divider, Alert, Tooltip, Select } from 'antd';
import { DatabaseOutlined, GithubOutlined, BranchesOutlined, FolderOutlined, KeyOutlined, SaveOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useAppStore } from '@/store';
import { useServiceContext } from '@/contexts/ServiceContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { servicesAPI } from '@/api/client';
import CodeIndexingControl from '@/components/CodeIndexing/CodeIndexingControl';
import { useEffect } from 'react';

const Settings = () => {
  const { theme, setTheme, refreshIntervals, setRefreshInterval } = useAppStore();
  const { selectedService } = useServiceContext();
  const [form] = Form.useForm();
  const [gitForm] = Form.useForm();
  const queryClient = useQueryClient();

  // Fetch service details when service is selected
  const { data: serviceDetails } = useQuery({
    queryKey: ['service', selectedService],
    queryFn: () => selectedService ? servicesAPI.get(selectedService) : Promise.resolve(null),
    enabled: !!selectedService,
  });

  // Reset form when serviceDetails changes
  useEffect(() => {
    if (serviceDetails) {
      gitForm.setFieldsValue({
        use_api_mode: serviceDetails.use_api_mode || false,
        repository_url: serviceDetails.repository_url || '',
        git_provider: serviceDetails.git_provider || null,
        git_branch: serviceDetails.git_branch || 'main',
        git_repo_path: serviceDetails.git_repo_path || '',
        access_token: serviceDetails.access_token || '',
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceDetails]);

  // Update Git configuration mutation
  const updateGitConfigMutation = useMutation({
    mutationFn: ({ serviceId, config }: { serviceId: string; config: any }) =>
      servicesAPI.update(serviceId, config),
    onSuccess: () => {
      message.success('Git configuration saved successfully');
      queryClient.invalidateQueries({ queryKey: ['service', selectedService] });
      queryClient.invalidateQueries({ queryKey: ['codeIndexingStatus', selectedService] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to save Git configuration');
    },
  });

  const handleSaveGitConfig = async () => {
    if (!selectedService || !serviceDetails) return;
    
    try {
      const values = await gitForm.validateFields();
      updateGitConfigMutation.mutate({
        serviceId: selectedService,
        config: {
          name: serviceDetails.name, // Required field
          description: serviceDetails.description,
          version: serviceDetails.version,
          use_api_mode: values.use_api_mode || false,
          repository_url: values.repository_url || null,
          git_provider: values.git_provider || null,
          git_branch: values.git_branch || 'main',
          git_repo_path: values.git_repo_path || null,
          access_token: values.access_token || null,
        },
      });
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  const handleSave = () => {
    message.success('Settings saved successfully');
  };

  return (
    <div>
      <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, marginBottom: 24 }}>Settings</h1>
      
      {!selectedService ? (
        // Show service selection prompt when no service is selected
        <div>
          <Alert
            message="Service Required"
            description="Please select a service from the header dropdown to view and manage service-specific settings."
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <DatabaseOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
            <h3 style={{ color: '#8c8c8c', marginBottom: 8 }}>Select a Service</h3>
            <p style={{ color: '#bfbfbf', fontSize: 14 }}>
              Choose a service to configure its specific settings and preferences.
            </p>
          </div>
        </div>
      ) : (
        <div>
          {/* Service Information */}
          {serviceDetails && (
            <Card title={`Service: ${serviceDetails.name}`} style={{ marginBottom: 16 }}>
              <Form layout="vertical">
                <Form.Item label="Service ID">
                  <Input value={serviceDetails.id} disabled />
                </Form.Item>
                <Form.Item label="Description">
                  <Input value={serviceDetails.description || 'No description'} disabled />
                </Form.Item>
                <Form.Item label="Repository URL">
                  <Input value={serviceDetails.repository_url || 'Not configured'} disabled />
                </Form.Item>
                <Form.Item label="Status">
                  <Space>
                    <Switch checked={serviceDetails.is_active} disabled />
                    <span>{serviceDetails.is_active ? 'Active' : 'Inactive'}</span>
                  </Space>
                </Form.Item>
              </Form>
            </Card>
          )}

          {/* Git Repository Configuration */}
          <Card 
            title={
              <Space>
                <GithubOutlined />
                <span>Git Repository Configuration</span>
              </Space>
            } 
            style={{ marginBottom: 16 }}
          >
            <Alert
              message="Configure Git repository for code indexing and exception correlation"
              description="Code indexing analyzes your codebase to provide better context for exceptions and RCA generation. Choose between Local Mode (clone repository) or API Mode (fetch via GitHub/GitLab API without local storage)."
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
            
            <Form 
              form={gitForm} 
              layout="vertical"
            >
              <Divider orientation="left">Code Indexing Configuration</Divider>
              
              <Alert
                message="Two Indexing Modes Available"
                description={
                  <div>
                    <p><strong>Local Mode:</strong> Reads files from a local directory path. You manage git clone/pull manually.</p>
                    <p><strong>API Mode:</strong> Fetches files via Git API (GitHub/GitLab). No local storage needed.</p>
                  </div>
                }
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />
              
              <Form.Item 
                label={
                  <Space>
                    <DatabaseOutlined />
                    <span>Indexing Mode</span>
                  </Space>
                }
                name="use_api_mode"
                valuePropName="checked"
                tooltip="Toggle between Local Mode (reads from disk) and API Mode (fetches via API)"
              >
                <Switch 
                  checkedChildren="API Mode (In-Memory)" 
                  unCheckedChildren="Local Mode (Disk)"
                  onChange={(checked) => {
                    // Update form to show/hide relevant fields
                    gitForm.setFieldsValue({ use_api_mode: checked });
                  }}
                />
              </Form.Item>
              
              <Form.Item 
                label={
                  <Space>
                    <GithubOutlined />
                    <span>Repository URL</span>
                  </Space>
                }
                name="repository_url"
                tooltip="Git repository URL (e.g., https://github.com/org/repo.git)"
                rules={[
                  { required: true, message: 'Repository URL is required' },
                  {
                    pattern: /^(https?:\/\/|git@)[\w\-.]+(:\d+)?\/([\w\-]+)\/([\w\-]+)(\.git)?$/,
                    message: 'Please enter a valid Git repository URL (e.g., https://github.com/org/repo.git)'
                  }
                ]}
              >
                <Input 
                  placeholder="https://github.com/organization/repository.git"
                  prefix={<GithubOutlined style={{ color: '#8c8c8c' }} />}
                />
              </Form.Item>
              
              <Form.Item
                noStyle
                shouldUpdate={(prevValues, currentValues) => prevValues.use_api_mode !== currentValues.use_api_mode}
              >
                {({ getFieldValue }) => {
                  const useApiMode = getFieldValue('use_api_mode');
                  
                  // Only show git_provider for API Mode
                  return useApiMode ? (
                    <Form.Item 
                      label={
                        <Space>
                          <GithubOutlined />
                          <span>Git Provider</span>
                        </Space>
                      }
                      name="git_provider"
                      tooltip="Select your Git hosting provider (GitHub or GitLab). Required for API Mode."
                      rules={[
                        { required: true, message: 'Git provider is required for API Mode' }
                      ]}
                    >
                      <Select
                        placeholder="Select Git provider"
                        options={[
                          { 
                            value: 'github', 
                            label: (
                              <Space>
                                <GithubOutlined />
                                <span>GitHub</span>
                              </Space>
                            )
                          },
                          { 
                            value: 'gitlab', 
                            label: (
                              <Space>
                                <GithubOutlined />
                                <span>GitLab</span>
                              </Space>
                            )
                          }
                        ]}
                      />
                    </Form.Item>
                  ) : null;
                }}
              </Form.Item>
              
              <Form.Item 
                label={
                  <Space>
                    <BranchesOutlined />
                    <span>Branch</span>
                  </Space>
                }
                name="git_branch"
                tooltip="Git branch to index (e.g., main, develop, master)"
                rules={[{ required: true, message: 'Branch name is required' }]}
              >
                <Input 
                  placeholder="main"
                  prefix={<BranchesOutlined style={{ color: '#8c8c8c' }} />}
                />
              </Form.Item>
              
              <Form.Item 
                noStyle
                shouldUpdate={(prevValues, currentValues) => prevValues.use_api_mode !== currentValues.use_api_mode}
              >
                {({ getFieldValue }) => {
                  const useApiMode = getFieldValue('use_api_mode');
                  
                  return !useApiMode ? (
                    <Form.Item 
                      label={
                        <Space>
                          <FolderOutlined />
                          <span>Local Repository Path</span>
                        </Space>
                      }
                      name="git_repo_path"
                      tooltip="Local path where repository files are located. Required for Local Mode."
                      rules={[
                        { required: true, message: 'Local path is required for Local Mode' },
                        {
                          pattern: /^(\/|[A-Za-z]:\\|\.{0,2}[\\/])?.+/,
                          message: 'Please enter an absolute path (e.g., /var/luffy/repos/my-service)'
                        }
                      ]}
                    >
                      <Input 
                        placeholder="/var/luffy/repos/my-service"
                        prefix={<FolderOutlined style={{ color: '#8c8c8c' }} />}
                      />
                    </Form.Item>
                  ) : null;
                }}
              </Form.Item>
              
              <Form.Item 
                label={
                  <Space>
                    <KeyOutlined />
                    <span>Access Token</span>
                  </Space>
                }
                name="access_token"
                tooltip="Access token for private repositories. Required for API Mode, optional for Local Mode."
              >
                <Input.Password 
                  placeholder="ghp_xxxxxxxxxxxxxxxxxxxx or glpat-xxxxxxxxxxxxxxxxxxxx"
                  prefix={<KeyOutlined style={{ color: '#8c8c8c' }} />}
                  visibilityToggle
                />
              </Form.Item>
              
              <Divider />
              
              <Form.Item 
                label={
                  <Space>
                    <KeyOutlined />
                    <span>Legacy Access Token (Deprecated)</span>
                  </Space>
                }
                name="git_access_token"
                tooltip="Legacy field. Use 'Access Token' above instead."
              >
                <Input.Password 
                  placeholder="Legacy token (use Access Token field above)"
                  prefix={<KeyOutlined style={{ color: '#8c8c8c' }} />}
                  visibilityToggle
                  disabled
                />
              </Form.Item>
              
              <Alert
                message="Automatic Code Indexing"
                description="Code indexing will be triggered automatically when exceptions are detected. No manual trigger needed."
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />
              
              <Form.Item>
                <Space>
                  <Button 
                    type="primary" 
                    icon={<SaveOutlined />}
                    onClick={handleSaveGitConfig}
                    loading={updateGitConfigMutation.isPending}
                  >
                    Save Git Configuration
                  </Button>
                  {serviceDetails?.repository_url && (
                    <Tooltip title="Git repository is configured">
                      <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
                    </Tooltip>
                  )}
                </Space>
              </Form.Item>
            </Form>
          </Card>

          {/* Code Indexing Control */}
          <div style={{ marginBottom: 16 }}>
            <CodeIndexingControl showHistory={true} />
          </div>

      <Card title="Appearance" style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label="Theme">
            <Space>
              <Switch
                checked={theme === 'dark'}
                onChange={(checked) => setTheme(checked ? 'dark' : 'light')}
              />
              <span>{theme === 'dark' ? 'Dark Mode' : 'Light Mode'}</span>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title="Refresh Intervals" style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical">
          <Form.Item
            label="Dashboard Refresh (seconds)"
            initialValue={refreshIntervals.dashboard / 1000}
          >
            <Input
              type="number"
              min={10}
              onChange={(e) => setRefreshInterval('dashboard', parseInt(e.target.value) * 1000)}
            />
          </Form.Item>

          <Form.Item
            label="Clusters Refresh (seconds)"
            initialValue={refreshIntervals.clusters / 1000}
          >
            <Input
              type="number"
              min={10}
              onChange={(e) => setRefreshInterval('clusters', parseInt(e.target.value) * 1000)}
            />
          </Form.Item>

          <Form.Item
            label="Tasks Refresh (seconds)"
            initialValue={refreshIntervals.tasks / 1000}
          >
            <Input
              type="number"
              min={5}
              onChange={(e) => setRefreshInterval('tasks', parseInt(e.target.value) * 1000)}
            />
          </Form.Item>
        </Form>
      </Card>

      <Card title="API Configuration" style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label="API Base URL" initialValue="http://localhost:8000/api/v1">
            <Input placeholder="http://localhost:8000/api/v1" />
          </Form.Item>

          <Form.Item label="Request Timeout (ms)" initialValue={30000}>
            <Input type="number" placeholder="30000" />
          </Form.Item>
        </Form>
      </Card>

          <Button type="primary" onClick={handleSave}>
            Save Settings
          </Button>
        </div>
      )}
    </div>
  );
};

export default Settings;

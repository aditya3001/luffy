import React, { useState } from 'react';
import { Card, Button, Space, Tag, Typography, message, Modal, Checkbox, Spin, Tooltip, Alert } from 'antd';
import {
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  CodeOutlined,
  BranchesOutlined,
  HistoryOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { codeIndexingAPI } from '@/api/client';
import { useServiceContext } from '@/contexts/ServiceContext';

const { Title, Text, Paragraph } = Typography;

interface CodeIndexingControlProps {
  showHistory?: boolean;
}

const CodeIndexingControl: React.FC<CodeIndexingControlProps> = ({ showHistory = true }) => {
  const { selectedService } = useServiceContext();
  const queryClient = useQueryClient();
  const [forceFull, setForceFull] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  // Fetch indexing status
  const { data: status, isLoading: statusLoading, error: statusError } = useQuery({
    queryKey: ['codeIndexingStatus', selectedService],
    queryFn: () => selectedService ? codeIndexingAPI.getStatus(selectedService) : Promise.resolve(null),
    enabled: !!selectedService,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Fetch indexing history
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['codeIndexingHistory', selectedService],
    queryFn: () => selectedService ? codeIndexingAPI.getHistory(selectedService, 5) : Promise.resolve(null),
    enabled: !!selectedService && showHistoryModal,
  });

  // Trigger indexing mutation
  const triggerMutation = useMutation({
    mutationFn: ({ serviceId, forceFull }: { serviceId: string; forceFull: boolean }) =>
      codeIndexingAPI.trigger(serviceId, forceFull),
    onSuccess: (data) => {
      message.success(`Code indexing triggered successfully! Task ID: ${data.task_id}`);
      queryClient.invalidateQueries({ queryKey: ['codeIndexingStatus'] });
      setForceFull(false);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to trigger code indexing');
    },
  });

  // Enable/Disable mutations
  const enableMutation = useMutation({
    mutationFn: (serviceId: string) => codeIndexingAPI.enable(serviceId),
    onSuccess: () => {
      message.success('Code indexing enabled');
      queryClient.invalidateQueries({ queryKey: ['codeIndexingStatus'] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to enable code indexing');
    },
  });

  const disableMutation = useMutation({
    mutationFn: (serviceId: string) => codeIndexingAPI.disable(serviceId),
    onSuccess: () => {
      message.warning('Code indexing disabled');
      queryClient.invalidateQueries({ queryKey: ['codeIndexingStatus'] });
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || 'Failed to disable code indexing');
    },
  });

  const handleTrigger = () => {
    if (!selectedService) {
      message.warning('Please select a service first');
      return;
    }

    // Use a local variable to track forceFull selection
    let forceFullIndexing = false;

    const modal = Modal.confirm({
      title: 'Trigger Code Indexing',
      content: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Paragraph>
            This will trigger code indexing for <Text strong>{status?.service_name}</Text>.
          </Paragraph>
          <Checkbox
            defaultChecked={false}
            onChange={(e) => {
              forceFullIndexing = e.target.checked;
              // Update modal button text
              modal.update({
                okText: forceFullIndexing ? 'Full Re-Index' : 'Incremental Index',
              });
            }}
          >
            Force full re-indexing (slower, but ensures complete index)
          </Checkbox>
          <Alert
            message="Incremental indexing will only process changed files since last index"
            type="info"
            showIcon
          />
        </Space>
      ),
      onOk: () => {
        triggerMutation.mutate({ serviceId: selectedService, forceFull: forceFullIndexing });
      },
      okText: 'Incremental Index',
      okButtonProps: { loading: triggerMutation.isPending },
    });
  };

  const handleToggleEnabled = () => {
    if (!selectedService) return;

    if (status?.code_indexing_enabled) {
      Modal.confirm({
        title: 'Disable Code Indexing',
        content: `Are you sure you want to disable code indexing for ${status.service_name}? This will prevent automatic indexing when exceptions are detected.`,
        onOk: () => disableMutation.mutate(selectedService),
        okText: 'Disable',
        okButtonProps: { danger: true },
      });
    } else {
      enableMutation.mutate(selectedService);
    }
  };

  const getStatusTag = () => {
    if (!status) return null;

    const statusConfig: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
      not_indexed: { color: 'default', icon: <ClockCircleOutlined />, text: 'Not Indexed' },
      indexing: { color: 'processing', icon: <LoadingOutlined />, text: 'Indexing...' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: 'Completed' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: 'Failed' },
    };

    const config = statusConfig[status.status] || statusConfig.not_indexed;

    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  if (!selectedService) {
    return (
      <Card>
        <Alert
          message="No Service Selected"
          description="Please select a service from the header to manage code indexing"
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
        />
      </Card>
    );
  }

  if (statusLoading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">Loading indexing status...</Text>
          </div>
        </div>
      </Card>
    );
  }

  if (statusError) {
    return (
      <Card>
        <Alert
          message="Error Loading Status"
          description="Failed to load code indexing status. Please try again."
          type="error"
          showIcon
        />
      </Card>
    );
  }

  return (
    <>
      <Card
        title={
          <Space>
            <CodeOutlined />
            <span>Code Indexing Control</span>
          </Space>
        }
        extra={
          <Space>
            {status?.code_indexing_enabled ? (
              <Tag color="success">Enabled</Tag>
            ) : (
              <Tag color="default">Disabled</Tag>
            )}
            {getStatusTag()}
          </Space>
        }
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* Service Info */}
          <div>
            <Title level={5}>Service: {status?.service_name}</Title>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">Repository: </Text>
                <Text code>{status?.git_repo_path || 'Not configured'}</Text>
              </div>
              <div>
                <Text type="secondary">Branch: </Text>
                <Tag icon={<BranchesOutlined />}>{status?.git_branch || 'main'}</Tag>
              </div>
            </Space>
          </div>

          {/* Indexing Status */}
          <div>
            <Title level={5}>Indexing Status</Title>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">Last Indexed: </Text>
                <Text>{formatDate(status?.last_indexed_at || null)}</Text>
              </div>
              {status?.last_indexed_commit && (
                <div>
                  <Text type="secondary">Commit: </Text>
                  <Text code>{status.last_indexed_commit.substring(0, 8)}</Text>
                </div>
              )}
              {status?.indexing_trigger && (
                <div>
                  <Text type="secondary">Last Trigger: </Text>
                  <Tag>{status.indexing_trigger.replace('_', ' ')}</Tag>
                </div>
              )}
              {status?.indexing_error && (
                <Alert
                  message="Indexing Error"
                  description={status.indexing_error}
                  type="error"
                  showIcon
                  closable
                />
              )}
            </Space>
          </div>

          {/* Actions */}
          <Space wrap>
            <Tooltip title={!status?.git_repo_path ? 'No Git repository configured' : ''}>
              <Button
                type="primary"
                icon={<SyncOutlined />}
                onClick={handleTrigger}
                loading={triggerMutation.isPending}
                disabled={status?.status === 'indexing'}
              >
                Trigger Indexing
              </Button>
            </Tooltip>

            <Button
              type={status?.code_indexing_enabled ? 'default' : 'primary'}
              onClick={handleToggleEnabled}
              loading={enableMutation.isPending || disableMutation.isPending}
            >
              {status?.code_indexing_enabled ? 'Disable' : 'Enable'} Auto-Indexing
            </Button>

            {showHistory && (
              <Button
                icon={<HistoryOutlined />}
                onClick={() => setShowHistoryModal(true)}
              >
                View History
              </Button>
            )}
          </Space>

          {/* Info Alert */}
          <Alert
            message="On-Demand Indexing"
            description={
              <Space direction="vertical" size="small">
                <Text>
                  Code indexing is triggered automatically when exceptions are detected.
                  You can also trigger it manually using the button above.
                </Text>
                <Text type="secondary">
                  • Incremental indexing only processes changed files (fast)
                </Text>
                <Text type="secondary">
                  • Full re-indexing processes all files (slower, but complete)
                </Text>
                <Text type="secondary">
                  • Minimum 5-minute interval between indexing operations
                </Text>
              </Space>
            }
            type="info"
            showIcon
          />
        </Space>
      </Card>

      {/* History Modal */}
      <Modal
        title={
          <Space>
            <HistoryOutlined />
            <span>Indexing History</span>
          </Space>
        }
        open={showHistoryModal}
        onCancel={() => setShowHistoryModal(false)}
        footer={[
          <Button key="close" onClick={() => setShowHistoryModal(false)}>
            Close
          </Button>,
        ]}
        width={700}
      >
        {historyLoading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin />
          </div>
        ) : history && history.history.length > 0 ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {history.history.map((record, index) => (
              <Card key={index} size="small">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <div>
                    <Text strong>Repository: </Text>
                    <Text>{record.repository}</Text>
                  </div>
                  <div>
                    <Text strong>Indexed At: </Text>
                    <Text>{formatDate(record.last_indexed_at)}</Text>
                  </div>
                  <div>
                    <Text strong>Commit: </Text>
                    <Text code>{record.last_indexed_commit?.substring(0, 8) || 'N/A'}</Text>
                  </div>
                  <div>
                    <Text strong>Files: </Text>
                    <Text>{record.total_files_indexed}</Text>
                    <Text strong style={{ marginLeft: 16 }}>Blocks: </Text>
                    <Text>{record.total_blocks_indexed}</Text>
                  </div>
                  <div>
                    <Text strong>Mode: </Text>
                    <Tag color={record.indexing_mode === 'full' ? 'orange' : 'blue'}>
                      {record.indexing_mode || 'unknown'}
                    </Tag>
                  </div>
                </Space>
              </Card>
            ))}
          </Space>
        ) : (
          <Alert
            message="No History"
            description="No indexing history available for this service"
            type="info"
            showIcon
          />
        )}
      </Modal>
    </>
  );
};

export default CodeIndexingControl;

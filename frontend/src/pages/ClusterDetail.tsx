import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Card,
  Descriptions,
  Tag,
  Space,
  Button,
  Spin,
  Alert,
  Typography,
  Divider,
  List,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  CopyOutlined,
  CloseCircleOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { format } from 'date-fns';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { clusterAPI, rcaAPI } from '@/api/client';

const { Title, Paragraph, Text } = Typography;

const ClusterDetail = () => {
  const { clusterId } = useParams<{ clusterId: string }>();
  const navigate = useNavigate();

  const { data: cluster, isLoading, error, refetch } = useQuery({
    queryKey: ['cluster', clusterId],
    queryFn: () => clusterAPI.get(clusterId!),
    enabled: !!clusterId,
  });

  const generateRCAMutation = useMutation({
    mutationFn: () => rcaAPI.generate(clusterId!),
    onSuccess: () => {
      message.success('RCA generation started. Redirecting...');
      setTimeout(() => {
        navigate(`/rca/${clusterId}`);
      }, 1500);
    },
    onError: () => {
      message.error('Failed to generate RCA');
    },
  });

  const skipMutation = useMutation({
    mutationFn: () => clusterAPI.skip(clusterId!),
    onSuccess: () => {
      message.success('Exception marked as skipped');
      refetch();
    },
    onError: () => {
      message.error('Failed to skip exception');
    },
  });

  const resolveMutation = useMutation({
    mutationFn: () => clusterAPI.resolve(clusterId!),
    onSuccess: () => {
      message.success('Exception marked as resolved');
      refetch();
    },
    onError: () => {
      message.error('Failed to resolve exception');
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: () => clusterAPI.reactivate(clusterId!),
    onSuccess: () => {
      message.success('Exception reactivated');
      refetch();
    },
    onError: () => {
      message.error('Failed to reactivate exception');
    },
  });

  const severityColors = {
    critical: 'red',
    high: 'orange',
    medium: 'gold',
    low: 'blue',
  };

  const statusColors = {
    active: 'error',
    skipped: 'default',
    resolved: 'success',
  };

  type StatusType = 'active' | 'skipped' | 'resolved';

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success('Copied to clipboard');
  };

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error || !cluster) {
    return (
      <Alert
        message="Error Loading Cluster"
        description="Failed to load cluster details. Please try again."
        type="error"
        showIcon
      />
    );
  }

  return (
    <div>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/clusters')}
        style={{ marginBottom: 16 }}
      >
        Back to Clusters
      </Button>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={2} style={{ margin: 0 }}>
              {cluster.exception_type}
            </Title>
            <Space style={{ marginTop: 8 }}>
              <Tag color={severityColors[cluster.severity]} style={{ textTransform: 'uppercase' }}>
                {cluster.severity}
              </Tag>
              <Tag color={statusColors[cluster.status as StatusType]} style={{ textTransform: 'capitalize' }}>
                {cluster.status || 'active'}
              </Tag>
              <Tag>{cluster.count} occurrences</Tag>
            </Space>
          </div>

          <Space>
            {cluster.has_rca ? (
              <Button
                type="primary"
                icon={<EyeOutlined />}
                onClick={() => navigate(`/rca/${clusterId}`)}
              >
                View RCA
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={() => generateRCAMutation.mutate()}
                loading={generateRCAMutation.isPending}
              >
                Generate RCA
              </Button>
            )}
            
            {cluster.status === 'active' && (
              <>
                <Button
                  icon={<CloseCircleOutlined />}
                  onClick={() => skipMutation.mutate()}
                  loading={skipMutation.isPending}
                >
                  Skip Exception
                </Button>
                <Button
                  icon={<CheckCircleOutlined />}
                  onClick={() => resolveMutation.mutate()}
                  loading={resolveMutation.isPending}
                  type="default"
                >
                  Mark as Resolved
                </Button>
              </>
            )}
            
            {(cluster.status === 'skipped' || cluster.status === 'resolved') && (
              <Button
                icon={<ReloadOutlined />}
                onClick={() => reactivateMutation.mutate()}
                loading={reactivateMutation.isPending}
              >
                Reactivate
              </Button>
            )}
          </Space>
        </div>

        <Divider />

        <Descriptions column={2} bordered>
          <Descriptions.Item label="Cluster ID">
            <code>{cluster.cluster_id}</code>
          </Descriptions.Item>
          <Descriptions.Item label="Exception Type">{cluster.exception_type}</Descriptions.Item>
          <Descriptions.Item label="First Seen">
            {format(new Date(cluster.first_seen), 'PPpp')}
          </Descriptions.Item>
          <Descriptions.Item label="Last Seen">
            {format(new Date(cluster.last_seen), 'PPpp')}
          </Descriptions.Item>
          <Descriptions.Item label="Affected Services" span={2}>
            <Space wrap>
              {(cluster.services ?? []).map((service) => (
                <Tag key={service} color="blue">
                  {service}
                </Tag>
              ))}
              {(cluster.services == null || cluster.services.length === 0) && (
                <span style={{ color: '#999' }}>No services</span>
              )}
            </Space>
          </Descriptions.Item>

        </Descriptions>
      </Card>

      <Card title="Exception Message" style={{ marginBottom: 16 }}>
        <Paragraph>
          <Text code copyable>
            {cluster.exception_message || 'No message available'}
          </Text>
        </Paragraph>
      </Card>

      <Card
        title="Stack Trace"
        extra={
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={() => copyToClipboard(JSON.stringify(cluster.stack_trace, null, 2))}
          >
            Copy
          </Button>
        }
        style={{ marginBottom: 16 }}
      >
        <div style={{ maxHeight: 300, overflow: 'auto' }}>
          <SyntaxHighlighter
            language="java"
            style={vscDarkPlus}
            customStyle={{ margin: 0, borderRadius: 4 }}
          >
            {cluster.stack_trace && cluster.stack_trace.length > 0
              ? cluster.stack_trace
                  .map(
                    (frame) =>
                      `at ${frame.symbol} (${frame.file}:${frame.line})`
                  )
                  .join('\n')
              : 'No stack trace available'}
          </SyntaxHighlighter>
        </div>
      </Card>



      {cluster.sample_logs && cluster.sample_logs.length > 0 && (
        <Card title="Sample Log Entries">
          <List
            dataSource={cluster.sample_logs}
            renderItem={(log) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color={log.level === 'ERROR' ? 'red' : 'default'}>{log.level}</Tag>
                      <Text type="secondary">{format(new Date(log.timestamp), 'PPpp')}</Text>
                      <Tag color="blue">{log.service}</Tag>
                    </Space>
                  }
                  description={<code style={{ fontSize: 12 }}>{log.message}</code>}
                />
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  );
};

export default ClusterDetail;

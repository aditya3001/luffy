import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Card,
  Button,
  Space,
  Spin,
  Alert,
  Typography,
  Divider,
  List,
  Tag,
  Rate,
  Input,
  Form,
  message,
  Descriptions,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  BulbOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import { format } from 'date-fns';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { rcaAPI } from '@/api/client';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const RCAView = () => {
  const { clusterId } = useParams<{ clusterId: string }>();
  const navigate = useNavigate();
  const [showFeedback, setShowFeedback] = useState(false);
  const [form] = Form.useForm();

  const { data: rca, isLoading, error } = useQuery({
    queryKey: ['rca', clusterId],
    queryFn: () => rcaAPI.get(clusterId!),
    enabled: !!clusterId,
    refetchInterval: (data) => (data ? false : 2000), // Poll every 2s if no data
  });

  const feedbackMutation = useMutation({
    mutationFn: (values: any) =>
      rcaAPI.submitFeedback({
        cluster_id: clusterId!,
        rca_id: rca?.cluster_id || clusterId!,
        ...values,
      }),
    onSuccess: () => {
      message.success('Thank you for your feedback!');
      setShowFeedback(false);
      form.resetFields();
    },
    onError: () => {
      message.error('Failed to submit feedback');
    },
  });

  const handleFeedback = async (isHelpful: boolean) => {
    if (isHelpful) {
      await feedbackMutation.mutateAsync({ is_helpful: true });
    } else {
      setShowFeedback(true);
    }
  };

  const handleSubmitFeedback = async () => {
    try {
      const values = await form.validateFields();
      await feedbackMutation.mutateAsync({
        is_helpful: false,
        ...values,
      });
    } catch (error) {
      console.error('Validation failed:', error);
    }
  };

  if (isLoading || !rca) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}>
          <Text type="secondary">
            {!rca ? 'Generating RCA... This may take a few moments.' : 'Loading RCA...'}
          </Text>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        message="Error Loading RCA"
        description="Failed to load RCA. The analysis may not have been generated yet."
        type="error"
        showIcon
        action={
          <Button onClick={() => navigate(`/clusters/${clusterId}`)}>
            Back to Cluster
          </Button>
        }
      />
    );
  }

  return (
    <div>
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(`/clusters/${clusterId}`)}
        style={{ marginBottom: 16 }}
      >
        Back to Cluster
      </Button>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={2} style={{ margin: 0 }}>
              Root Cause Analysis
            </Title>
            <Text type="secondary">
              {rca.generated_at
                    ? `Generated on ${format(new Date(rca.generated_at), 'PPpp')}`
                    : 'Generated date not available'}
            </Text>
            {rca.confidence_score && (
              <div style={{ marginTop: 8 }}>
                <Tag color="blue">Confidence: {(rca.confidence_score * 100).toFixed(0)}%</Tag>
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card title={<><BulbOutlined /> Root Cause</>} style={{ marginBottom: 16 }}>
        {rca.root_cause?.explanation ? (
          <Paragraph style={{ fontSize: 15, lineHeight: 1.8 }}>
            {rca.root_cause.explanation}
          </Paragraph>
        ) : (
          <Text type="secondary">Root cause explanation not available</Text>
        )}
      </Card>

      {rca.impact_analysis && (
        <Card title="Impact Analysis" style={{ marginBottom: 16 }}>
          <Descriptions column={1}>
            <Descriptions.Item label="Affected Services">
            <Space wrap>
              {(rca.impact_analysis?.affected_services || []).map((service: string) => (
                <Tag key={service} color="red">
                  {service}
                </Tag>
              ))}
              {(!rca.impact_analysis?.affected_services ||
                rca.impact_analysis.affected_services.length === 0) && (
                <Text type="secondary">No services affected</Text>
              )}
            </Space>
          </Descriptions.Item>

            <Descriptions.Item label="User Impact">
              {rca.impact_analysis.user_impact}
            </Descriptions.Item>
            {rca.impact_analysis.business_impact && (
              <Descriptions.Item label="Business Impact">
                {rca.impact_analysis.business_impact}
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>
      )}

      <Card title="Recommendations" style={{ marginBottom: 16 }}>
        <List
          dataSource={rca.recommendations}
          renderItem={(recommendation, index) => (
            <List.Item>
              <List.Item.Meta
                avatar={
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: '50%',
                      background: '#1890ff',
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 'bold',
                    }}
                  >
                    {index + 1}
                  </div>
                }
                description={<Text style={{ fontSize: 14 }}>{recommendation}</Text>}
              />
            </List.Item>
          )}
        />
      </Card>

      {rca.code_snippets && rca.code_snippets.length > 0 && (
        <Card title={<><CodeOutlined /> Code Context</>} style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {rca.code_snippets.map((snippet, index) => (
              <div key={index}>
                <div style={{ marginBottom: 8 }}>
                  <Text strong>{snippet.file}</Text>
                  <Text type="secondary"> (Line {snippet.line})</Text>
                </div>
                <SyntaxHighlighter
                  language={snippet.language || 'java'}
                  style={vscDarkPlus}
                  customStyle={{ margin: 0, borderRadius: 4 }}
                  showLineNumbers
                  startingLineNumber={snippet.line}
                >
                  {typeof snippet.code === 'string' ? snippet.code : JSON.stringify(snippet.code)}
                </SyntaxHighlighter>

              </div>
            ))}
          </Space>
        </Card>
      )}

      <Card title="Was this helpful?">
        {!showFeedback ? (
          <Space>
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => handleFeedback(true)}
              loading={feedbackMutation.isPending}
            >
              Yes, helpful
            </Button>
            <Button
              icon={<CloseCircleOutlined />}
              onClick={() => handleFeedback(false)}
            >
              No, not helpful
            </Button>
          </Space>
        ) : (
          <Form form={form} layout="vertical">
            <Form.Item
              label="Accuracy Rating"
              name="accuracy_rating"
              rules={[{ required: true, message: 'Please rate the accuracy' }]}
            >
              <Rate />
            </Form.Item>

            <Form.Item label="Comments" name="comments">
              <TextArea
                rows={4}
                placeholder="Please tell us what could be improved..."
              />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  onClick={handleSubmitFeedback}
                  loading={feedbackMutation.isPending}
                >
                  Submit Feedback
                </Button>
                <Button onClick={() => setShowFeedback(false)}>Cancel</Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Card>
    </div>
  );
};

export default RCAView;
